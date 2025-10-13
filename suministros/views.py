# suministros/views.py
"""
Vistas generales (home) de la aplicación Suministros.

Modo normal (staff/superuser):
- KPI de compras/ventas y tabla de reposición (como ya tenías).

Modo cliente:
- Muestra saludo + gráfica de SUS compras (en realidad sus "ventas" registradas),
  y oculta los KPIs y la tabla.
"""

from datetime import timedelta
from django.shortcuts import render
from django.utils import timezone
from django.db.models import Sum, F

from compras.models import Compra
from inventario.models import Producto, Proveedor

# 👇 Necesario para el modo cliente (sus compras = sus ventas)
from ventas.models import Venta, VentaProducto



def _es_cliente(user) -> bool:
    """
    Cliente = usuario autenticado que NO es staff ni superuser.
    (No dependemos de permisos; basta con 'activo')
    """
    return bool(user.is_authenticated and not user.is_staff and not user.is_superuser)


def index(request):
    """
    Home:
    - Si es cliente: saludo + gráfica de últimos 30 días de sus compras.
    - Si NO es cliente: home 'pro' original con KPIs y tabla.
    """
    user = request.user

    if _es_cliente(user):
        # ------- Serie últimos 30 días para ESTE usuario -------
        hoy = timezone.localdate()
        hace_30 = hoy - timedelta(days=29)  # 30 días incluyendo hoy

        # ⚠️ Si el FK hacia usuario en Venta NO se llama 'cliente', cambia 'cliente_id' aquí.
        ventas_qs = Venta.objects.filter(
            cliente_id=user.pk,
            fecha__gte=hace_30,
            fecha__lte=hoy,
        ).values("fecha").annotate(total=Sum("total")).order_by("fecha")

        # Eje X completo (aunque no haya ventas algunos días)
        dias = [hace_30 + timedelta(days=i) for i in range(30)]
        idx = {row["fecha"]: float(row["total"] or 0) for row in ventas_qs}
        labels = [d.strftime("%d-%m") for d in dias]
        data = [idx.get(d, 0.0) for d in dias]

        # Top 5 productos del cliente (por cantidad)
        top_qs = (
            VentaProducto.objects
            .filter(venta__cliente_id=user.pk, venta__fecha__gte=hace_30, venta__fecha__lte=hoy)
            .values(nombre=F("producto__nombre"))
            .annotate(cantidad=Sum("cantidad"))
            .order_by("-cantidad")[:5]
        )

        chart = {
            "labels": labels,
            "ventas": data,  # serie principal
            "top_labels": [it["nombre"] for it in top_qs],
            "top_data": [int(it["cantidad"] or 0) for it in top_qs],
        }

        contexto = {
            "es_cliente": True,
            "nombre_cliente": (user.get_full_name() or user.username),
            "chart": chart,
        }
        return render(request, "index.html", contexto)

    # ------- Modo normal (lo que ya tenías) -------
    contexto = {
        "compras_count": Compra.objects.count(),
        "productos_count": Producto.objects.count(),
        "proveedores_count": Proveedor.objects.count(),
        # KPIs rápidos (hoy y mes) para el home normal
        "compras_hoy": Compra.objects.filter(fecha__date=timezone.localdate()).aggregate(s=Sum("total"))["s"] or 0,
        "ventas_hoy":  Venta.objects.filter(fecha=timezone.localdate()).aggregate(s=Sum("total"))["s"] or 0,
        "compras_mes": Compra.objects.filter(fecha__date__gte=timezone.localdate().replace(day=1)).aggregate(s=Sum("total"))["s"] or 0,
        "ventas_mes":  Venta.objects.filter(fecha__gte=timezone.localdate().replace(day=1)).aggregate(s=Sum("total"))["s"] or 0,
        "es_cliente": False,
    }
    return render(request, "index.html", contexto)