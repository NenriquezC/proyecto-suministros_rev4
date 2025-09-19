from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from . forms import ProveedorForm  # NUEVO
from django.http import HttpResponse  # si no está ya
# inventario/views.py
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_GET
from .models import Producto  # ajusta si tu modelo tiene otro nombre



@login_required
@permission_required("inventario.add_proveedor", raise_exception=True)
def proveedor_crear(request):
    next_url = request.GET.get("next") or reverse("compras:agregar_compra")

    if request.method == "POST":
        form = ProveedorForm(request.POST)
        if form.is_valid():
            proveedor = form.save()
            messages.success(request, f"Proveedor “{proveedor}” creado y preseleccionado.")
            # Redirige de vuelta a compras/crear con proveedor_id para preseleccionar
            separator = "&" if "?" in next_url else "?"
            return redirect(f"{next_url}{separator}proveedor_id={proveedor.pk}")
    else:
        form = ProveedorForm()

    return render(
        request,
        "inventario/proveedores/crear_proveedor/crear_proveedor.html",
        {"form": form},
    )
def inventario(request):
    return HttpResponse("Inventario OK")  # placeholder temporal

def listar_productos(request):
    return HttpResponse("Listado de productos (placeholder)")

# Si también tienes estas rutas en urls.py, crea sus placeholders ya:
def listar_proveedores(request):
    return HttpResponse("Listado de proveedores (placeholder)")

def crear_producto(request):
    return HttpResponse("Crear producto (placeholder)")

def agregar_producto(request):
    return HttpResponse("Crear producto (placeholder)")
def editar_producto(request, pk):
    return HttpResponse("Crear producto (placeholder)")
def eliminar_producto(request, pk):
    return HttpResponse("Crear producto (placeholder)")
#inventario/views.py----------------------------------------------------------------------------
#Qué: crear una vista GET que responda {"id":…, "nombre":…, "precio_unitario": …}.
#Por qué: el front pedirá “¿cuál es el precio del producto X?” y rellenará el input.
@require_GET
def producto_precio_api(request, pk):
    """
    Devuelve info mínima del producto en JSON.
    Respuesta: {id, nombre, precio_unitario}
    """

    try:
        p= Producto.objects.get(pk=pk)
    except Producto.DoesNotExist:
        raise Http404("El producto no existe")
    
    #AJUSTA ESTE NOMBRE DE CAMPO al real de tu modelo:
    #   - precio_unitario
    #   - precio_compra
    #   - costo, etc.
    precio = getattr(p, "precio_compra", None) #obtiene el valor del atributo

    return JsonResponse({
        "id": p.pk,
        "nombre": getattr(p, "nombre", str(p)),
        "precio_unitario": float(precio or 0),
    })
