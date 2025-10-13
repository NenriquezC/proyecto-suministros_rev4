"""
Vistas del panel (dashboard) e índice simple.

Responsabilidades:
- Calcular KPIs rápidas (hoy/mes), series temporales y tablas auxiliares.
- Preparar payloads listos para templates (incl. json_script para charts).
- Mantener consultas eficientes y legibles con anotaciones/aggregates.

Diseño:
- Sin cambiar lógica de negocio: sólo documentación y organización.
- Usar `timezone` para fechas seguras y `Coalesce` para valores nulos.
"""

# dashboard/views.py
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.utils import timezone

from compras.models import Compra
from ventas.models import Venta, VentaProducto
from inventario.models import Producto


# ─────────────────────────────────────────────────────────────────────────────
# VISTA: panel
# Propósito: Renderizar el dashboard principal con KPIs, top vendidos, low stock
#            y series de los últimos 14 días (compras/ventas).
# ─────────────────────────────────────────────────────────────────────────────
@login_required
def panel(request):
    """
    Calcula y entrega datos para el dashboard (/dashboard/panel).

    Flujo:
    1) Fechas de referencia: hoy, inicio de mes, y rango de 14 días.
    2) KPIs rápidas: totales de hoy y del mes (compras/ventas), contadores.
    3) Top productos vendidos (cantidad).
    4) Low stock: productos con stock ≤ stock_minimo.
    5) Series 14 días: compras (TruncDate) y ventas.
    6) Prepara payload `chart` para `json_script` en el template.

    Parámetros:
    request (HttpRequest)

    Retorna:
    HttpResponse: render("dashboard/panel.html", contexto)

    Notas:
    - Se respeta tu distinción Compra.fecha (DateTime) vs Venta.fecha (Date).
    - `Decimal("0")` previene `None` en agregaciones.
    - `labels`, `data_compras`, `data_ventas` se conservan también por separado
        aunque el template consuma `chart`.
    """
    tznow = timezone.now()
    hoy = tznow.date()
    inicio_mes = hoy.replace(day=1)
    hace_14 = hoy - timedelta(days=13)  # 14 días con hoy

    # ───────────────── KPIs rápidas ─────────────────
    compras_hoy = Compra.objects.filter(fecha__date=hoy).aggregate(s=Sum("total"))["s"] or Decimal("0")
    ventas_hoy  = Venta.objects.filter(fecha=hoy).aggregate(s=Sum("total"))["s"] or Decimal("0")

    compras_mes = Compra.objects.filter(fecha__date__gte=inicio_mes).aggregate(s=Sum("total"))["s"] or Decimal("0")
    ventas_mes  = Venta.objects.filter(fecha__gte=inicio_mes).aggregate(s=Sum("total"))["s"] or Decimal("0")

    productos_activos = Producto.objects.count()
    proveedores_activos = Producto.objects.values("proveedor_id").distinct().count()
    compras_count = Compra.objects.count()
    ventas_count  = Venta.objects.count()

    # ──────────────── Top productos vendidos (cantidad) ────────────────
    top_vendidos_qs = (
        VentaProducto.objects
        .values(nombre=F("producto__nombre"))
        .annotate(cantidad=Sum("cantidad"))
        .order_by("-cantidad")[:5]
    )
    _top_vendidos_list = list(top_vendidos_qs)
    top_labels = [it["nombre"] for it in _top_vendidos_list]
    top_data   = [int(it["cantidad"] or 0) for it in _top_vendidos_list]

    # ──────────────── Low stock (stock <= stock_minimo) ────────────────
    low_stock = (
        Producto.objects
        .filter(stock_minimo__isnull=False)
        .filter(stock__lte=F("stock_minimo"))
        .order_by(F("stock") - F("stock_minimo"))[:10]
        .values("id", "nombre", "stock", "stock_minimo")
    )

    # ──────────────── Series últimos 14 días (compras/ventas) ──────────
    serie_compras = (
        Compra.objects
        .filter(fecha__date__gte=hace_14, fecha__date__lte=hoy)
        .annotate(d=TruncDate("fecha"))
        .values("d")
        .annotate(total=Sum("total"))
        .order_by("d")
    )
    serie_ventas = (
        Venta.objects
        .filter(fecha__gte=hace_14, fecha__lte=hoy)
        .values("fecha")
        .annotate(total=Sum("total"))
        .order_by("fecha")
    )

    # Eje X común de fechas
    dias = [hace_14 + timedelta(days=i) for i in range(14)]
    idx_c = {r["d"]: r["total"] for r in serie_compras}
    idx_v = {r["fecha"]: r["total"] for r in serie_ventas}

    data_compras = [float(idx_c.get(d, 0) or 0) for d in dias]
    data_ventas  = [float(idx_v.get(d, 0) or 0) for d in dias]
    labels = [d.strftime("%d-%m") for d in dias]

    # Payload para el json_script del template
    chart = {
        "labels": labels,
        "compras": data_compras,
        "ventas": data_ventas,
        "top_labels": top_labels,
        "top_data": top_data,
    }

    contexto = {
        # KPIs
        "compras_hoy": compras_hoy,
        "ventas_hoy": ventas_hoy,
        "compras_mes": compras_mes,
        "ventas_mes": ventas_mes,
        "productos_activos": productos_activos,
        "proveedores_activos": proveedores_activos,
        "compras_count": compras_count,
        "ventas_count": ventas_count,

        # tablas
        "top_vendidos": _top_vendidos_list,
        "low_stock": list(low_stock),

        # charts
        "labels": labels,             # opcional si solo usas 'chart' en el template
        "data_compras": data_compras, # opcional
        "data_ventas": data_ventas,   # opcional
        "chart": chart,               # <-- lo que consume {{ chart|json_script:"chart-data" }}
    }
    return render(request, "dashboard/panel.html", contexto)


# ─────────────────────────────────────────────────────────────────────────────
# VISTA: index
# Propósito: Página de inicio simple con totales del día/mes y low stock (stock ≤ mínimo).
#            No incluye “contactar proveedor” en esta versión.
# ─────────────────────────────────────────────────────────────────────────────
def index(request):
    """
    Renderiza el índice simple (/) con totales y lista resumida de low stock.

    Flujo:
    1) Cálculo de hoy e inicio de mes (y primer día del mes siguiente).
    2) Totales HOY/MES para comprasy ventas (con Coalesce a 0).
    3) Low stock: productos con stock ≤ stock_minimo (incluye igualdad).
    4) Render de `index.html` con el contexto.

    Parámetros:
    request (HttpRequest)

    Retorna:
    HttpResponse: render("index.html", contexto)

    Notas:
    - Venta.fecha se asume Date; Compra.fecha se filtra por `fecha__date`.
    - Se prioriza claridad: `Coalesce(Sum(...), Value(0))` con DecimalField.
    """
    from django.db.models import F, Sum, Case, When, Value, IntegerField, DecimalField
    from django.db.models.functions import Coalesce

    hoy = timezone.localdate()
    inicio_mes = hoy.replace(day=1)
    next_month = (inicio_mes + timedelta(days=32)).replace(day=1)

    # Totales HOY (Compra.fecha suele ser DateTimeField; Venta.fecha suele ser DateField)
    compras_hoy = (
        Compra.objects.filter(fecha__date=hoy)
        .aggregate(s=Coalesce(Sum("total"), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2)))
        .get("s")
    )
    ventas_hoy = (
        Venta.objects.filter(fecha=hoy)
        .aggregate(s=Coalesce(Sum("total"), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2)))
        .get("s")
    )

    # Totales MES
    compras_mes = (
        Compra.objects.filter(fecha__date__gte=inicio_mes, fecha__date__lt=next_month)
        .aggregate(s=Coalesce(Sum("total"), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2)))
        .get("s")
    )
    ventas_mes = (
        Venta.objects.filter(fecha__gte=inicio_mes, fecha__lt=next_month)
        .aggregate(s=Coalesce(Sum("total"), Value(0), output_field=DecimalField(max_digits=12, decimal_places=2)))
        .get("s")
    )

    # Productos para contactar proveedor: **stock <= stock_minimo** (incluye iguales)
    low_stock_contact = (
        Producto.objects.select_related("proveedor")
        .filter(stock_minimo__isnull=False)
        .filter(stock__lte=F("stock_minimo"))
        .annotate(
            deficit=Case(
                When(stock__lt=F("stock_minimo"), then=F("stock_minimo") - F("stock")),
                default=Value(0),
                output_field=IntegerField(),  # ambos campos son enteros -> mantenemos entero
            )
        )
        .order_by((F("stock") - F("stock_minimo")).asc(), "nombre")[:20]
    )

    contexto = {
        "compras_hoy": compras_hoy,
        "ventas_hoy": ventas_hoy,
        "compras_mes": compras_mes,
        "ventas_mes": ventas_mes,
        "low_stock_contact": low_stock_contact,  # en index ahora incluye los == mínimo
    }
    return render(request, "index.html", contexto)