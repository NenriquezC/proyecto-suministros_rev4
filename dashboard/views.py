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


@login_required
def panel(request):
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
    top_vendidos = (
        VentaProducto.objects
        .values(nombre=F("producto__nombre"))
        .annotate(cantidad=Sum("cantidad"))
        .order_by("-cantidad")[:5]
    )

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
        "top_vendidos": list(top_vendidos),
        "low_stock": list(low_stock),

        # charts
        "labels": labels,
        "data_compras": data_compras,
        "data_ventas": data_ventas,
    }
    return render(request, "dashboard/panel.html", contexto)


# ======== INDEX SIMPLE (solo totales) – SIN "contactar proveedor" ========
# dashboard/views.py  -> solo la función index
def index(request):
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