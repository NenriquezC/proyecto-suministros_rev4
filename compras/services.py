# compras/services.py
"""
Servicios (reglas de negocio) para la app 'compras'.

Responsabilidades:
- Cálculo y persistencia de totales (subtotal, impuesto_total, total).
- Actualización consistente de stock ante creación/edición de compras.
- Utilidades de redondeo monetario.

Diseño:
- Todas las operaciones que afecten stock/valores se envuelven en transacciones atómicas.
- La UI (views/forms) NO debe duplicar estas reglas: aquí vive la “fuente de verdad”.
"""

from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Tuple
from django.db import transaction
from django.db.models import F, Sum, DecimalField, ExpressionWrapper
from django.core.exceptions import ValidationError
from .models import Compra, CompraProducto
from inventario.models import Producto


# # ─────────────────────────────────────────────────────────────────────────────
# Utilidades
# ─────────────────────────────────────────────────────────────────────────────

def redondear_moneda(importe: Decimal) -> Decimal:
    """
    Redondea un importe a 2 decimales con HALF_UP (regla típica financiera).
    Args:
    importe: Decimal a redondear.
    Returns:
    Decimal con 2 decimales.
    """
    return importe.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ─────────────────────────────────────────────────────────────────────────────
# Stock helpers (atómico + anti-negativos)
# ─────────────────────────────────────────────────────────────────────────────

def _aplicar_delta_stock_seguro(producto_id: int, delta_unidades):
    """
    Aplica un delta al stock del Producto de forma segura.
    Estrategia:
    1) Actualiza stock con F() (evita condiciones de carrera en suma/resta).
    2) Bloquea la fila con select_for_update() y verifica que no quede negativo.
    3) Si quedó negativo, revierte el delta y lanza ValidationError.
    Args:
    producto_id: PK del producto a actualizar.
    delta_unidades: Entero (positivo suma, negativo resta). Si es 0 o None, no hace nada.
    Raises:
    ValidationError: Si el producto no existe o si el stock resultante es negativo.
    """
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


# ─────────────────────────────────────────────────────────────────────────────
# Totales de la compra
# ─────────────────────────────────────────────────────────────────────────────
"""@transaction.atomic
def calcular_y_guardar_totales_compra(compra: Compra,tasa_impuesto_pct: Decimal | None = None,) -> Compra:
    
    Calcula subtotal, impuesto_total (opcional) y total de una compra y los persiste.
    Reglas:
    - subtotal = Σ(cantidad * precio_unitario) de las líneas (con precisión intermedia).
    - impuesto_total:
        * Si 'tasa_impuesto_pct' es un número (p.ej. 0.19 para 19%), se recalcula como:
            impuesto_total = redondear(subtotal * tasa_impuesto_pct)
        * Si es None, NO se recalcula (se respeta lo que venga de UI o estado previo).
    - total = redondear(subtotal - descuento_total + impuesto_total)
    - Todo se guarda con 2 decimales (redondeo HALF_UP).
    Args:
    compra: Instancia de Compra ya persistida (PK existente).
    tasa_impuesto_pct: Decimal o None. Si se pasa, se fuerza el recálculo del impuesto.
    Returns:
    La misma instancia 'compra' con campos 'subtotal', 'impuesto_total' (si corresponde) y 'total' actualizados.
    
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
    return compra"""
@transaction.atomic
def calcular_y_guardar_totales_compra(
    compra: Compra,
    tasa_impuesto_pct: Decimal | None = None,
) -> Compra:
    """
    Calcula y persiste: subtotal, descuento_total (desde %), impuesto_total y total.
    Impuesto se calcula sobre (subtotal - descuento).
    """
    from decimal import Decimal
    from django.db.models import F, Sum, DecimalField, ExpressionWrapper

    # Subtotal desde líneas
    total_linea_expr = ExpressionWrapper(
        F("cantidad") * F("precio_unitario"),
        output_field=DecimalField(max_digits=16, decimal_places=6),
    )
    agregados = CompraProducto.objects.filter(compra=compra).aggregate(subtotal=Sum(total_linea_expr))
    subtotal_calculado = agregados["subtotal"] or Decimal("0")

    # Descuento: DERIVAR SIEMPRE desde porcentaje
    pct = Decimal(compra.descuento_porcentaje or 0) / Decimal("100")
    descuento_total = redondear_moneda(subtotal_calculado * pct)

    # Base imponible
    base = subtotal_calculado - descuento_total
    if base < 0:
        base = Decimal("0.00")

    # Impuesto: si recibimos tasa (0.23) lo recalculamos sobre la base
    if tasa_impuesto_pct is not None:
        compra.impuesto_total = redondear_moneda(base * Decimal(str(tasa_impuesto_pct)))

    # Totales
    compra.subtotal = redondear_moneda(subtotal_calculado)
    compra.descuento_total = descuento_total
    importe_impuesto = compra.impuesto_total or Decimal("0.00")
    compra.total = redondear_moneda(base + importe_impuesto)

    compra.save(update_fields=["subtotal", "descuento_total", "impuesto_total", "total"])
    return compra

# ─────────────────────────────────────────────────────────────────────────────
# Stock en creación de compra
# ─────────────────────────────────────────────────────────────────────────────

@transaction.atomic
def aplicar_stock_despues_de_crear_compra(compra: Compra) -> None:
    """
    Ajusta stock tras crear una compra y actualiza metadata del producto.
    Efectos por línea:
    - Suma 'cantidad' al stock del producto.
    - Actualiza 'precio_compra' con el último costo registrado.
    - Ajusta 'stock_minimo' simple: 90% del stock total si supera el mínimo actual.
    Args:
        compra: Instancia de Compra recién creada (con líneas ya guardadas).
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


# ─────────────────────────────────────────────────────────────────────────────
# Stock en edición de compra
# ─────────────────────────────────────────────────────────────────────────────
@transaction.atomic
def reconciliar_stock_tras_editar_compra(
    compra: Compra,
    lineas_previas: Dict[int, Tuple[int, Decimal]],
) -> None:
    """
    Reconciliación de stock tras editar una compra (agregar/quitar/modificar líneas).
    Estrategia:
    - Líneas eliminadas: restar su cantidad del producto “viejo”.
    - Líneas nuevas: sumar su cantidad al producto “nuevo”.
    - Líneas persistentes:
        * Si el producto no cambió → aplicar delta de cantidades.
        * Si cambió de producto → restar al anterior y sumar al nuevo.
    Args:
        compra: Instancia editada de Compra (líneas actuales ya guardadas).
        lineas_previas: Snapshot previo {pk_linea: (producto_id, cantidad)} tomado antes de guardar.
    Raises:
        ValidationError: Si alguna operación deja stock negativo (propagada desde helper).
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