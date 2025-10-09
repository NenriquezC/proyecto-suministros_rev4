# ventas/services.py
from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Tuple

from django.db import transaction
from django.db.models import F, Sum, DecimalField, ExpressionWrapper
from django.core.exceptions import ValidationError

from .models import Venta, VentaProducto
from inventario.models import Producto

from django.db.models.functions import Least


# ==== Utilidades ====

def _round2(v: Decimal) -> Decimal:
    return Decimal(v or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ==== Helper: ajuste de stock seguro (atómico + anti-negativos) ====

ALLOW_SOFT_MINIMO_EN_VENTA = True  # política blanda en ventas

def _aplicar_delta_stock_seguro(producto_id: int, delta_unidades):
    """
    Ajusta el stock de forma atómica.

    Reglas:
    - Nunca permite stock negativo (bloquea).
    - Si delta < 0 (venta) y el nuevo stock quedaría por debajo del stock_minimo:
        * Con política BLANDA (ALLOW_SOFT_MINIMO_EN_VENTA=True): baja automáticamente
        stock_minimo al nuevo stock en la MISMA UPDATE (LEAST) para no violar el CHECK.
        * Con política DURA: lanza ValidationError.
    """
    if not delta_unidades:
        return

    with transaction.atomic():
        prod = Producto.objects.select_for_update().get(pk=producto_id)
        stock_actual = prod.stock or 0
        nuevo_stock = stock_actual + delta_unidades

        # 1) Nunca stock negativo
        if nuevo_stock < 0:
            raise ValidationError(
                f"Stock insuficiente para '{prod}'. Disponible: {stock_actual}, "
                f"requerido: {abs(delta_unidades)}."
            )

        # 2) ¿quedaría por debajo del mínimo?
        queda_bajo_minimo = (prod.stock_minimo is not None) and (nuevo_stock < prod.stock_minimo)

        if delta_unidades < 0 and queda_bajo_minimo and ALLOW_SOFT_MINIMO_EN_VENTA:
            # Política BLANDA: clamp de mínimo en misma UPDATE
            filas = Producto.objects.filter(pk=producto_id).update(
                stock=F("stock") + delta_unidades,
                stock_minimo=Least(F("stock_minimo"), F("stock") + delta_unidades),
            )
        else:
            # Política DURA (o no cae bajo mínimo)
            if queda_bajo_minimo:
                raise ValidationError(
                    f"La operación dejaría el stock ({nuevo_stock}) por debajo del "
                    f"mínimo ({prod.stock_minimo}) para '{prod}'."
                )
            filas = Producto.objects.filter(pk=producto_id).update(
                stock=F("stock") + delta_unidades
            )

        if filas == 0:
            raise ValidationError(f"No existe Producto id={producto_id}.")

# ==== Totales de la venta ====

@transaction.atomic
def calcular_y_guardar_totales_venta(
    venta: Venta,
    tasa_impuesto_pct: Decimal | None = None
) -> Venta:
    total_linea_expr = ExpressionWrapper(
        F("cantidad") * F("precio_unitario") * (1 - (F("descuento") / 100.0)),
        output_field=DecimalField(max_digits=16, decimal_places=6),
    )
    agg = VentaProducto.objects.filter(venta=venta).aggregate(subtotal=Sum(total_linea_expr))
    subtotal_calc = agg["subtotal"] or Decimal("0")

    venta.subtotal = _round2(subtotal_calc)

    if tasa_impuesto_pct is not None:
        venta.impuesto = _round2(subtotal_calc * Decimal(str(tasa_impuesto_pct)))

    desc = venta.descuento_total or Decimal("0")
    imp  = venta.impuesto or Decimal("0")
    venta.total = _round2(venta.subtotal - desc + imp)

    venta.save(update_fields=["subtotal", "impuesto", "total"])
    return venta


# ==== Stock en creación de venta (no depende de related_name) ====

@transaction.atomic
def aplicar_stock_despues_de_crear_venta(venta: Venta) -> None:
    """
    Resta del stock la cantidad de cada línea de venta.
    """
    for linea in VentaProducto.objects.select_related("producto").filter(venta=venta).order_by("id"):
        _aplicar_delta_stock_seguro(linea.producto_id, -linea.cantidad)  # resta


# ==== Stock en edición de venta (no depende de related_name) ====

@transaction.atomic
def reconciliar_stock_tras_editar_venta(
    venta: Venta,
    lineas_previas: Dict[int, Tuple[int, Decimal]],
) -> None:
    """
    - Eliminadas  → devolver al producto viejo (+cantidad_anterior).
    - Nuevas      → restar del producto nuevo (-cantidad_actual).
    - Persisten   → si mismo producto: restar delta; si cambió: devolver viejo y restar nuevo.
    """
    lineas_actuales_qs = VentaProducto.objects.filter(venta=venta)
    lineas_actuales = {l.pk: (l.producto_id, l.cantidad) for l in lineas_actuales_qs}

    pks_previas   = set(lineas_previas.keys())
    pks_actuales  = set(lineas_actuales.keys())
    pks_eliminadas = pks_previas - pks_actuales
    pks_nuevas     = pks_actuales - pks_previas
    pks_persisten  = pks_previas & pks_actuales

    for pk in pks_eliminadas:
        prod_id_anterior, cant_anterior = lineas_previas[pk]
        _aplicar_delta_stock_seguro(prod_id_anterior, +cant_anterior)

    for pk in pks_nuevas:
        prod_id_actual, cant_actual = lineas_actuales[pk]
        _aplicar_delta_stock_seguro(prod_id_actual, -cant_actual)

    for pk in pks_persisten:
        prod_id_antes, cant_antes = lineas_previas[pk]
        prod_id_ahora,  cant_ahora = lineas_actuales[pk]
        if prod_id_antes == prod_id_ahora:
            delta = -(cant_ahora - cant_antes)
            _aplicar_delta_stock_seguro(prod_id_ahora, delta)
        else:
            _aplicar_delta_stock_seguro(prod_id_antes, +cant_antes)
            _aplicar_delta_stock_seguro(prod_id_ahora, -cant_ahora)