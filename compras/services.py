# compras/services.py
from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Tuple

from django.db import transaction
from django.db.models import F, Sum, DecimalField, ExpressionWrapper
from django.core.exceptions import ValidationError

from .models import Compra, CompraProducto
from inventario.models import Producto


# ==== Utilidades ====

def redondear_moneda(importe: Decimal) -> Decimal:
    return importe.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ==== Helper: aplicar delta seguro al stock (atómico + anti-negativos) ====

def _aplicar_delta_stock_seguro(producto_id: int, delta_unidades):
    if not delta_unidades:
        return
    filas = Producto.objects.filter(pk=producto_id).update(stock=F("stock") + delta_unidades)
    if filas == 0:
        raise ValidationError(f"No existe Producto id={producto_id}.")
    prod_lock = Producto.objects.select_for_update().get(pk=producto_id)
    if prod_lock.stock < 0:
        Producto.objects.filter(pk=producto_id).update(stock=F("stock") - delta_unidades)
        raise ValidationError(
            f"Stock negativo para '{prod_lock}'. Delta={delta_unidades}, resultante={prod_lock.stock}."
        )


# ==== Totales de la compra ====

@transaction.atomic
def calcular_y_guardar_totales_compra(
    compra: Compra,
    tasa_impuesto_pct: Decimal | None = None,
) -> Compra:
    total_linea_expr = ExpressionWrapper(
        F("cantidad") * F("precio_unitario"),
        output_field=DecimalField(max_digits=16, decimal_places=6),
    )
    agregados = CompraProducto.objects.filter(compra=compra).aggregate(subtotal=Sum(total_linea_expr))
    subtotal_calculado = agregados["subtotal"] or Decimal("0")

    if tasa_impuesto_pct is not None:
        compra.impuesto_total = redondear_moneda(subtotal_calculado * Decimal(str(tasa_impuesto_pct)))

    compra.subtotal = redondear_moneda(subtotal_calculado)
    importe_descuento = compra.descuento_total or Decimal("0")
    importe_impuesto  = compra.impuesto_total  or Decimal("0")
    compra.total = redondear_moneda(compra.subtotal - importe_descuento + importe_impuesto)

    compra.save(update_fields=["subtotal", "impuesto_total", "total"])
    return compra


# ==== Stock en creación de compra (no depende de related_name) ====

@transaction.atomic
def aplicar_stock_despues_de_crear_compra(compra: Compra) -> None:
    """
    Suma la cantidad de cada línea al stock del producto (usa F()) y actualiza precio_compra.
    """
    for linea in CompraProducto.objects.select_related("producto").filter(compra=compra).order_by("id"):
        _aplicar_delta_stock_seguro(linea.producto_id, linea.cantidad)  # suma
        # actualizar último costo y mínimo
        producto = Producto.objects.select_for_update().get(pk=linea.producto_id)
        producto.precio_compra = linea.precio_unitario
        # regla de reposición simple (90%)
        stock_total = int(producto.stock or 0)
        minimo_candidato = int(stock_total * 0.90)
        if minimo_candidato > int(producto.stock_minimo or 0):
            producto.stock_minimo = minimo_candidato
        producto.save(update_fields=["precio_compra", "stock_minimo"])


# ==== Stock en edición de compra (no depende de related_name) ====

@transaction.atomic
def reconciliar_stock_tras_editar_compra(
    compra: Compra,
    lineas_previas: Dict[int, Tuple[int, Decimal]],
) -> None:
    """
    - Eliminadas  → restar del producto viejo.
    - Nuevas      → sumar al producto nuevo.
    - Persisten   → si mismo producto: delta; si cambió: restar viejo y sumar nuevo.
    """
    lineas_actuales_qs = CompraProducto.objects.filter(compra=compra)
    lineas_actuales = {l.pk: (l.producto_id, l.cantidad) for l in lineas_actuales_qs}

    pks_previas   = set(lineas_previas.keys())
    pks_actuales  = set(lineas_actuales.keys())
    pks_eliminadas = pks_previas - pks_actuales
    pks_nuevas     = pks_actuales - pks_previas
    pks_persisten  = pks_previas & pks_actuales

    for pk in pks_eliminadas:
        prod_id_anterior, cant_anterior = lineas_previas[pk]
        _aplicar_delta_stock_seguro(prod_id_anterior, -cant_anterior)

    for pk in pks_nuevas:
        prod_id_actual, cant_actual = lineas_actuales[pk]
        _aplicar_delta_stock_seguro(prod_id_actual, +cant_actual)

    for pk in pks_persisten:
        prod_id_antes, cant_antes = lineas_previas[pk]
        prod_id_ahora,  cant_ahora = lineas_actuales[pk]
        if prod_id_antes == prod_id_ahora:
            delta = cant_ahora - cant_antes
            _aplicar_delta_stock_seguro(prod_id_ahora, delta)
        else:
            _aplicar_delta_stock_seguro(prod_id_antes, -cant_antes)
            _aplicar_delta_stock_seguro(prod_id_ahora, +cant_ahora)