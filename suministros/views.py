# suministros/views.py
#esto solo lo genere para la pantalla principal de home paara que tenga un formato mas pro
from django.shortcuts import render
from compras.models import Compra
from inventario.models import Producto, Proveedor
# Si quieres proteger la home:
# from django.contrib.auth.decorators import login_required

# @login_required
def index(request):
    contexto = {
        "compras_count": Compra.objects.count(),
        "productos_count": Producto.objects.count(),
        "proveedores_count": Proveedor.objects.count(),
    }
    return render(request, "index.html", contexto)