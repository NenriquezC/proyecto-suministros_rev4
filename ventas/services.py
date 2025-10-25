# ventas/services.py
"""
Servicios (reglas de negocio) para la app 'ventas'.

Propósito:
    Centralizar la lógica crítica de VENTAS: cálculo de totales y ajustes de stock
    (creación/edición), manteniendo views/forms como orquestadores finos.

Responsabilidades:
    - Cálculo y persistencia de subtotal, impuesto y total de una venta.
    - Ajustes de stock tras crear/editar ventas (sumas/restas y reconciliaciones).
    - Redondeo financiero consistente (HALF_UP).

Diseño/Notas:
    - Todas las operaciones con efectos en stock/valores están dentro de transacciones.
    - Anti-negativos: nunca permitir stock < 0; política configurable para stock_mínimo.
    - Fórmulas:
        * subtotal := Σ cantidad * precio_unitario * (1 - descuento%/100) (por línea).
        * impuesto := base * tasa (si se provee tasa).
        * total    := subtotal - descuento_total + impuesto.
    - Este módulo es la “fuente de verdad” para importes/stock en Ventas.
"""
from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Tuple

from django.db import transaction
from django.db.models import F, Sum, DecimalField, ExpressionWrapper
from django.core.exceptions import ValidationError

from .models import Venta, VentaProducto
from inventario.models import Producto

from django.db.models.functions import Least


# ─────────────────────────────────────────────────────────────────────────────
# Utilidades
# ─────────────────────────────────────────────────────────────────────────────
def _round2(v: Decimal) -> Decimal:
    """
    Redondeo financiero a 2 decimales con HALF_UP.

    Args:
        v (Decimal): valor a redondear (permite None).

    Returns:
        Decimal: valor con exactamente 2 decimales.
    """
    return Decimal(v or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ─────────────────────────────────────────────────────────────────────────────
# Helper: ajuste de stock seguro (atómico + anti-negativos)
# ─────────────────────────────────────────────────────────────────────────────

ALLOW_SOFT_MINIMO_EN_VENTA = True  # política blanda en ventas

def _aplicar_delta_stock_seguro(producto_id: int, delta_unidades):
    """
    Aplica un delta al stock de Producto de forma SEGURA y transaccional.

    Reglas:
        - Nunca permite stock negativo (ValidationError).
        - Si delta < 0 (venta) y el nuevo stock rompe el mínimo:
            * Política BLANDA (ALLOW_SOFT_MINIMO_EN_VENTA=True):
                - Ajusta stock y reduce stock_minimo en la MISMA UPDATE
                con LEAST(stock_minimo, nuevo_stock) para no violar el CHECK.
            * Política DURA (False):
                - Lanza ValidationError si quedaría por debajo del mínimo.

    Args:
        producto_id (int): PK del producto a ajustar.
        delta_unidades (int | Decimal): suma/resta a aplicar (0/None → no-op).

    Raises:
        ValidationError: si el producto no existe, o el stock resultante es inválido.
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

# ─────────────────────────────────────────────────────────────────────────────
# Totales de la venta
# ─────────────────────────────────────────────────────────────────────────────
@transaction.atomic
def calcular_y_guardar_totales_venta(venta: Venta, tasa_impuesto_pct: Decimal | None = None) -> Venta:
    """
    Calcula y persiste `subtotal`, `impuesto` y `total` de una venta.

    Fórmulas:
        - subtotal := Σ (cantidad * precio_unitario * (1 - descuento%/100)).
        - impuesto := base * tasa, si `tasa_impuesto_pct` no es None.
            * base := subtotal (en esta versión), pues el descuento por línea ya está aplicado.
        - total := subtotal - descuento_total + impuesto.

    Args:
        venta (Venta): instancia existente con sus líneas.
        tasa_impuesto_pct (Decimal | None): tasa fraccional (0.23 para 23%), o None para preservar impuesto.

    Returns:
        Venta: instancia con campos actualizados y guardados.
    """
    total_linea_expr = ExpressionWrapper(
        F("cantidad") * F("precio_unitario") * (1 - (F("descuento") / 100.0)),
        output_field=DecimalField(max_digits=16, decimal_places=6),
    )
    agg = VentaProducto.objects.filter(venta=venta).aggregate(subtotal=Sum(total_linea_expr))
    subtotal_calc = agg["subtotal"] or Decimal("0")

    venta.subtotal = _round2(subtotal_calc)

    if tasa_impuesto_pct is not None:
        desc = venta.descuento_total or Decimal("0")
        base = max(Decimal("0"), subtotal_calc - desc)
        venta.impuesto = _round2(base * Decimal(str(tasa_impuesto_pct)))

    desc = venta.descuento_total or Decimal("0")
    imp  = venta.impuesto or Decimal("0")
    venta.total = _round2(venta.subtotal - desc + imp)

    venta.save(update_fields=["subtotal", "impuesto", "total"])
    return venta


# ─────────────────────────────────────────────────────────────────────────────
# Stock en creación de venta (no depende de related_name)
# ─────────────────────────────────────────────────────────────────────────────
@transaction.atomic
def aplicar_stock_despues_de_crear_venta(venta: Venta) -> None:
    """
    Ajusta stock tras crear una venta.

    Efectos:
        - Por cada línea: resta `cantidad` al stock del producto asociado.

    Args:
        venta (Venta): venta recién creada (líneas ya persistidas).
    """
    for linea in VentaProducto.objects.select_related("producto").filter(venta=venta).order_by("id"):
        _aplicar_delta_stock_seguro(linea.producto_id, -linea.cantidad)  # resta


# ─────────────────────────────────────────────────────────────────────────────
# Stock en edición de venta (no depende de related_name)
# ─────────────────────────────────────────────────────────────────────────────
@transaction.atomic
def reconciliar_stock_tras_editar_venta(venta: Venta, lineas_previas: Dict[int, Tuple[int, Decimal]],) -> None:
    """
    Reconciliación de stock tras editar la venta (agregar/quitar/modificar líneas).

    Estrategia:
        - Líneas eliminadas  → devolver al producto viejo (+cantidad_anterior).
        - Líneas nuevas      → restar del producto nuevo (-cantidad_actual).
        - Líneas persistentes:
            * Si mismo producto → restar delta (cant_ahora - cant_antes).
            * Si cambió producto → devolver al anterior y restar del nuevo.

    Args:
        venta (Venta): venta ya editada (líneas actuales persistidas).
        lineas_previas (dict[int, tuple[int, Decimal]]):
            Snapshot previo {pk_linea: (producto_id, cantidad)} tomado antes de guardar.

    Raises:
        ValidationError: propagada desde el helper si un ajuste deja estado inválido.
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