# compras/services.py
from __future__ import annotations # 
from decimal import Decimal, ROUND_HALF_UP # 
from typing import Dict, Tuple
from django.db import transaction 
from django.db.models import F, Sum, DecimalField, ExpressionWrapper
from .models import Compra, CompraProducto
from inventario.models import Producto


# ==== Utilidades ====

def redondear_moneda(importe: Decimal) -> Decimal:
    """
    Redondea un importe monetario a 2 decimales con HALF_UP (estándar contable).
    Por qué: para valores monetarios “normales” (2 decimales).
    """
    return importe.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ==== Totales de la compra ====

@transaction.atomic
def calcular_y_guardar_totales_compra(compra: Compra,tasa_impuesto_pct: Decimal | None = None,) -> Compra:
    """
    Recalcula y guarda los totales de una compra a partir de sus líneas.

    - subtotal = SUM(cantidad * precio_unitario)  (se calcula en la BD)
    - descuento_total: se respeta el valor que tenga la compra
    (si quieres manejar descuento_porcentaje, lo calculas antes y lo asignas).
    - impuesto_total: si 'tasa_impuesto_pct' viene, se recalcula como:
        impuesto_total = subtotal * tasa_impuesto_pct
    Si no viene, se deja el valor actual.
    - total = subtotal - descuento_total + impuesto_total
    -----------------------------------------------------------------------------------------------------------
    Qué hace:
    Suma en BD cada línea: cantidad * precio_unitario → subtotal_calculado.
    Si le pasas tasa_impuesto_pct (ej. Decimal("0.23")), recalcula impuesto_total = subtotal * tasa.
    Calcula total = subtotal - descuento_total + impuesto_total.
    Guarda subtotal, impuesto_total (si corresponde) y total ya redondeados.
    Variables clave:
    total_linea_expr: expresión SQL para sumar líneas sin traerlas a Python.
    agregados: resultado de la agregación con Sum.
    subtotal_calculado: subtotal bruto antes de redondear.
    importe_descuento / importe_impuesto: valores finales usados para total.
    Cuándo llamarla: justo después de guardar/editar las líneas.
    """

    # Expresión SQL para total por línea, con precisión extra durante el cálculo.
    total_linea_expr = ExpressionWrapper( F("cantidad") * F("precio_unitario"), output_field=DecimalField(max_digits=16, decimal_places=6),)
    agregados = (CompraProducto.objects.filter(compra=compra).aggregate(subtotal=Sum(total_linea_expr)))
    subtotal_calculado = agregados["subtotal"] or Decimal("0")
    # Impuesto: sólo lo recalculamos si la vista nos entrega la tasa.
    if tasa_impuesto_pct is not None:
        compra.impuesto_total = redondear_moneda(subtotal_calculado * Decimal(str(tasa_impuesto_pct)))

    # Subtotal oficial (redondeado)
    compra.subtotal = redondear_moneda(subtotal_calculado)

    # Total oficial
    importe_descuento = compra.descuento_total or Decimal("0")
    importe_impuesto  = compra.impuesto_total  or Decimal("0")
    compra.total = redondear_moneda(compra.subtotal - importe_descuento + importe_impuesto)

    compra.save(update_fields=["subtotal", "impuesto_total", "total"])
    return compra
#================================================================================================

def fijar_minimo_por_reposicion(producto) -> None:
    """
    Sube el stock_minimo si la reposición lo amerita.
    Nunca lo baja.
    """
    stock_total = int(producto.stock or 0)
    minimo_candidato = int(stock_total * 0.90)
    minimo_actual = int(producto.stock_minimo or 0)
    if minimo_candidato > minimo_actual:
        producto.stock_minimo = minimo_candidato




# ======================================== Stock (creación y edición) ============================

@transaction.atomic
def aplicar_stock_despues_de_crear_compra(compra: Compra) -> None:
    """
    Tras crear la compra y sus líneas:
    - Suma la cantidad de cada línea al stock del producto.
    - Actualiza 'precio' del producto como último costo (precio_unitario).
    - Marca la línea como aplicada (_stock_aplicado=True) para no duplicar.
    Qué hace:
    Para cada línea recién creada y aún no aplicada (_stock_aplicado=False):
    Suma la cantidad al stock del producto.
    Actualiza precio del producto al precio_unitario (estrategia “último costo”).
    Marca la línea como aplicada para no duplicar si se reintenta.
    Variables clave:
    linea._stock_aplicado: bandera anti-doble-suma.
    producto: se bloquea con select_for_update() para evitar carreras.
    Cuándo llamarla: al final del flujo de creación (no en edición).
    """
    for linea in compra.lineas.select_related("producto").order_by("id"):
        producto = Producto.objects.select_for_update().get(pk=linea.producto_id)

        producto.stock = (producto.stock or 0) + int(linea.cantidad)
        producto.precio_compra = linea.precio_unitario  # último costo

        # Recalcular mínimo de reposición (nunca baja)
        fijar_minimo_por_reposicion(producto)

        producto.save(update_fields=["stock", "precio_compra", "stock_minimo"])


#  =========================================================================================================================================



@transaction.atomic
def reconciliar_stock_tras_editar_compra(compra: Compra,lineas_previas: Dict[int, Tuple[int, Decimal]],) -> None:
    """
    Ajusta el stock después de editar una compra.

    'lineas_previas' es un diccionario con el estado ANTERIOR de las líneas:
        { linea_pk: (producto_id_anterior, cantidad_anterior) }

    Se compara contra el estado ACTUAL (después de guardar el formset):
    - Líneas eliminadas: restar su cantidad al producto antiguo.
    - Líneas nuevas: sumar su cantidad al producto nuevo.
    - Líneas que permanecen:
           * Si cambió el producto: restar al viejo y sumar al nuevo.
           * Si es el mismo producto: ajustar la diferencia de cantidades (delta).
    --------------------------------------------------------------------------------------------------------------------------
    Qué hace:
    Compara estado previo de líneas vs actual y ajusta stock:
    Eliminadas → resta del producto viejo.
    Nuevas → suma al producto nuevo.
    Persisten → si cambió la referencia, resta al viejo y suma al nuevo; si no, aplica delta de cantidad.
    Variables clave:
    lineas_previas: { linea_pk: (producto_id_anterior, cantidad_anterior) }. Lo tomas antes de guardar el formset.
    lineas_actuales: mapa actual después de guardar.
    pks_eliminadas, pks_nuevas, pks_persisten: conjuntos para cada caso.
    delta: diferencia de cantidad cuando el producto no cambió.
    Cuándo llamarla: tras guardar el formset en edición.
    """
    # Mapa con estado ACTUAL: {linea_pk: (producto_id_actual, cantidad_actual)}
    lineas_actuales = {l.pk: (l.producto_id, l.cantidad) for l in compra.lineas.all()}

    # 1) Eliminadas (estaban antes y ya no están)
    pks_eliminadas = set(lineas_previas.keys()) - set(lineas_actuales.keys())
    for pk in pks_eliminadas:
        prod_id_anterior, cant_anterior = lineas_previas[pk]
        producto = Producto.objects.select_for_update().get(pk=prod_id_anterior)
        producto.stock = (producto.stock or 0) - cant_anterior
        producto.save()

    # 2) Nuevas (no estaban antes y ahora sí)
    pks_nuevas = set(lineas_actuales.keys()) - set(lineas_previas.keys())
    for pk in pks_nuevas:
        prod_id_actual, cant_actual = lineas_actuales[pk]
        producto = Producto.objects.select_for_update().get(pk=prod_id_actual)
        producto.stock = (producto.stock or 0) + cant_actual
        producto.save()

    # 3) Persisten (ajustar por delta o cambio de producto)
    pks_persisten = set(lineas_actuales.keys()) & set(lineas_previas.keys())
    for pk in pks_persisten:
        prod_id_antes, cant_antes = lineas_previas[pk]
        prod_id_ahora,  cant_ahora  = lineas_actuales[pk]

        if prod_id_antes == prod_id_ahora:
            # Misma referencia → ajustar diferencia de cantidad
            delta = cant_ahora - cant_antes
            if delta != 0:
                producto = Producto.objects.select_for_update().get(pk=prod_id_ahora)
                producto.stock = (producto.stock or 0) + delta
                producto.save()
        else:
            # Cambió el producto → revertir al viejo y sumar al nuevo
            prod_viejo = Producto.objects.select_for_update().get(pk=prod_id_antes)
            prod_nuevo = Producto.objects.select_for_update().get(pk=prod_id_ahora)
            prod_viejo.stock = (prod_viejo.stock or 0) - cant_antes
            prod_nuevo.stock = (prod_nuevo.stock or 0) + cant_ahora
            prod_viejo.save()
            prod_nuevo.save()