"""
Vistas del panel (dashboard) e índice simple.

Propósito:
    Renderizar el dashboard principal y el índice con KPIs, series y tablas
    auxiliares, preparando payloads listos para templates (incl. json_script).

Responsabilidades:
    - Calcular KPIs rápidas (hoy/mes) de compras y ventas.
    - Armar series temporales (últimos 14 días) para charts.
    - Proveer tablas auxiliares: top vendidos, low stock, top proveedores.
    - Empaquetar datos en un 'chart' consumible por el template.

Dependencias/Assume:
    - Modelos: Compra, Venta, VentaProducto, Producto.
    - Campos: Compra.fecha (DateTime), Venta.fecha (Date), Producto.stock/_minimo.
    - El template del panel consume {{ chart|json_script:"chart-data" }}.

Diseño/Notas:
    - No se cambia lógica de negocio; solo documentación y organización.
    - Uso de timezone/TruncDate para fechas seguras.
    - Coalesce/Case/When para valores nulos y cálculos robustos.
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
from django.db.models import Avg, Case, When, DecimalField, ExpressionWrapper
from django.db.models.functions import TruncDate

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
        1) Fechas de referencia: hoy, inicio de mes, y rango 14 días (incluye hoy).
        2) KPIs rápidas: totales HOY/MES (compras/ventas) + contadores.
        3) Top productos vendidos por cantidad.
        4) Low stock: stock <= stock_minimo (top 10).
        5) Series 14 días: compras (TruncDate) y ventas (por fecha).
        6) Construye arrays 'labels', 'compras', 'ventas', 'top_*'.
        7) NUEVO: top proveedores por monto y descuento medio; añade 'supp_*' al payload.

    Args:
        request (HttpRequest): solicitud HTTP autenticada.

    Returns:
        HttpResponse: render("dashboard/panel.html", contexto) con:
            - KPIs: compras_hoy, ventas_hoy, compras_mes, ventas_mes, etc.
            - Tablas: top_vendidos, low_stock, top_proveedores_...
            - Chart payload: dict 'chart' listo para json_script.

    Notas:
        - Compra.fecha es DateTime -> filtra con fecha__date.
        - Venta.fecha es Date -> filtra directamente por rango de date.
        - Los floats en 'chart' facilitan consumo por JS en el template.
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

    # ──────────────── NUEVO: Top proveedores ────────────────
    # Top por monto comprado (€)
    top_proveedores_compras_qs = (
        Compra.objects
        .select_related("proveedor")
        .values("proveedor", "proveedor__nombre")
        .annotate(total=Sum("total"))
        .order_by("-total")[:5]
    )
    top_proveedores_compras = [
        {"nombre": it["proveedor__nombre"], "total": it["total"] or Decimal("0")}
        for it in top_proveedores_compras_qs
        if it["proveedor__nombre"] is not None
    ]

    # Top por descuento medio (%) = AVG( (descuento_total / subtotal) * 100 ) por proveedor
    descuento_pct_expr = ExpressionWrapper(
        Case(
            When(subtotal__gt=0, then=(F("descuento_total") / F("subtotal")) * Decimal("100")),
            default=Decimal("0"),
            output_field=DecimalField(max_digits=12, decimal_places=4),
        ),
        output_field=DecimalField(max_digits=12, decimal_places=4),
    )

    top_proveedores_descuento_qs = (
        Compra.objects
        .select_related("proveedor")
        .values("proveedor", "proveedor__nombre")
        .annotate(descuento_pct=Avg(descuento_pct_expr))
        .order_by("-descuento_pct")[:5]
    )
    top_proveedores_descuento = [
        {"nombre": it["proveedor__nombre"], "descuento_pct": it["descuento_pct"] or Decimal("0")}
        for it in top_proveedores_descuento_qs
        if it["proveedor__nombre"] is not None
    ]

    # Arrays para una posible gráfica de proveedores (opcional; el template los usará si existen)
    supp_labels    = [it["nombre"] for it in top_proveedores_compras]
    supp_amounts   = [float(it["total"]) for it in top_proveedores_compras]
    supp_discounts = [float(it["descuento_pct"]) for it in top_proveedores_descuento]

    # Payload para el json_script del template
    chart = {
        "labels": labels,
        "compras": data_compras,
        "ventas": data_ventas,
        "top_labels": top_labels,
        "top_data": top_data,
        # opcional (para gráfica de proveedores)
        "supp_labels": supp_labels,
        "supp_amounts": supp_amounts,
        "supp_discounts": supp_discounts,
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
        "top_proveedores_compras": top_proveedores_compras,         # NUEVO
        "top_proveedores_descuento": top_proveedores_descuento,     # NUEVO

        # charts
        "labels": labels,             # opcional si solo usas 'chart' en el template
        "data_compras": data_compras, # opcional
        "data_ventas": data_ventas,   # opcional
        "chart": chart,               # lo que consume {{ chart|json_script:"chart-data" }}
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
        1) Fechas de hoy, inicio de mes y primer día del mes siguiente.
        2) Totales HOY/MES para compras y ventas (Coalesce a 0).
        3) Low stock: productos con stock <= stock_minimo (incluye igualdad).
        4) Render de "index.html" con el contexto.

    Args:
        request (HttpRequest): solicitud HTTP.

    Returns:
        HttpResponse: render("index.html", contexto) con:
            - compras_hoy, ventas_hoy, compras_mes, ventas_mes
            - low_stock_contact (productos con déficit calculado)

    Notas:
        - Venta.fecha se asume Date; Compra.fecha se filtra por fecha__date.
        - Case/When produce 'deficit' entero para ordenación y visualización.
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