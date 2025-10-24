# compras/services.py
"""
Servicios (reglas de negocio) para la app 'compras'.

Propósito:
    Centralizar la lógica de negocio crítica (cálculo de totales y gestión de stock),
    manteniendo a views/forms como capas delgadas. Este módulo es la “fuente de
    verdad” para los importes y el stock.

Responsabilidades:
    - Cálculo y persistencia de subtotal, descuento_total, impuesto_total y total.
    - Ajustes de stock tras crear/editar compras (sumas, restas y reconciliaciones).
    - Utilidades de redondeo monetario coherentes en toda la app.

Dependencias/Assume:
    - Los modelos Compra y CompraProducto existen e integran validadores.
    - Producto en inventario expone `stock`, `precio_compra` y `stock_minimo`.
    - Se invocan estas funciones en transacciones atómicas cuando hay efectos
    sobre múltiples tablas (para evitar estados intermedios inconsistentes).

Diseño:
    - Transacciones atómicas alrededor de operaciones con efectos (stock/valores).
    - Redondeo HALF_UP para importes (convención financiera).
    - Cálculo de impuesto sobre la base: (subtotal - descuento_total).

Notas:
    - No se introducen side-effects fuera de lo declarado (p. ej., señales); las
    vistas o capas superiores deciden el momento de invocación.
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
        importe (Decimal): Importe a redondear.

    Returns:
        Decimal: Importe con exactamente 2 decimales (HALF_UP).

    Notas:
        - Mantener una única función de redondeo evita “sorpresas” al mezclar
        distintos modos/precisiones en la app.
    """
    return importe.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ─────────────────────────────────────────────────────────────────────────────
# Stock helpers (atómico + anti-negativos)
# ─────────────────────────────────────────────────────────────────────────────

def _aplicar_delta_stock_seguro(producto_id: int, delta_unidades):
    """
    Aplica un delta al stock del Producto de forma segura (con rollback si queda negativo).

    Estrategia:
        1) Actualiza el stock con F() → operación atómica y a prueba de carreras.
        2) Bloquea la fila (SELECT ... FOR UPDATE) para verificar resultado real.
        3) Si el stock queda negativo, revierte el delta y lanza ValidationError.

    Args:
        producto_id (int): PK del producto a actualizar.
        delta_unidades (int | Decimal): Cantidad a sumar/restar (0/None → no-op).

    Raises:
        ValidationError: Si el producto no existe o si el stock resultante es negativo.

    Notas:
        - La transacción atómica asegura que, si hay que revertir, no queden estados
        intermedios inconsistentes.
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
"""
@transaction.atomic
def calcular_y_guardar_totales_compra(compra: Compra,tasa_impuesto_pct: Decimal | None = None,) -> Compra:
    ...
    return compra
"""

@transaction.atomic
def calcular_y_guardar_totales_compra(compra: Compra,tasa_impuesto_pct: Decimal | None = None,) -> Compra:
    """
    Calcula y persiste subtotal, descuento_total (derivado de %), impuesto_total y total.

    Reglas:
        - subtotal := Σ(cantidad * precio_unitario) con precisión intermedia (6 decimales).
        - descuento_total := redondear(subtotal * (descuento_porcentaje/100)).
        - base := subtotal - descuento_total (no negativa).
        - impuesto_total:
            * Si `tasa_impuesto_pct` se pasa (p. ej., Decimal("0.23")), se recalcula
              como redondear(base * tasa).
            * Si es None, se preserva el valor existente en la compra.
        - total := redondear(base + impuesto_total).

    Args:
        compra (Compra): Instancia ya persistida (PK existente).
        tasa_impuesto_pct (Decimal | None): Tasa en forma fraccional (0.23 para 23%),
            o None para no tocar el impuesto_total.

    Returns:
        Compra: La misma instancia con campos actualizados y guardados.

    Notas:
        - El cálculo del impuesto se hace sobre la BASE después del descuento global.
        - Se actualizan exactamente los campos: subtotal, descuento_total, impuesto_total, total.
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
    Ajusta el stock tras crear una compra y actualiza metadata relevante del producto.

    Efectos por línea:
        - Suma 'cantidad' al stock del producto (anti-negativo).
        - Actualiza 'precio_compra' con el costo más reciente.
        - Ajusta 'stock_minimo' con una regla simple: 90% del stock total si supera
        el mínimo actual.

    Args:
        compra (Compra): Instancia recién creada (se asume que sus líneas ya existen).

    Raises:
        ValidationError: Propagada desde el helper si un ajuste deja stock negativo.

    Notas:
        - Se usa select_for_update() al retocar la metadata para evitar “pisadas”.
        - La regla del 90% es heurística simple; si cambian las políticas,
        centraliza aquí su actualización.
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
def reconciliar_stock_tras_editar_compra(compra: Compra,lineas_previas: Dict[int, Tuple[int, Decimal]],) -> None:
    """
    Reconciliación de stock tras editar una compra (agregar/quitar/modificar líneas).

    Estrategia:
        - Líneas eliminadas  → restar su cantidad del producto “viejo”.
        - Líneas nuevas      → sumar su cantidad al producto “nuevo”.
        - Líneas persistentes:
            * Si el producto no cambió → aplicar delta de cantidades.
            * Si cambió de producto     → restar al anterior y sumar al nuevo.

    Args:
        compra (Compra): Compra ya editada (líneas actuales están guardadas).
        lineas_previas (dict[int, tuple[int, Decimal]]):
            Snapshot previo {pk_linea: (producto_id, cantidad)} tomado antes de guardar.

    Raises:
        ValidationError: Si alguna operación deja stock negativo (propagado desde helper).

    Notas:
        - La reconciliación está pensada para minimizar los deltas aplicados y
        mantener coherencia incluso con ediciones complejas (cambios de producto).
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