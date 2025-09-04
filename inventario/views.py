from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from . forms import ProveedorForm  # NUEVO
from django.http import HttpResponse  # si no está ya

@login_required
@permission_required("inventario.add_proveedor", raise_exception=True)
def proveedor_crear(request):
    next_url = request.GET.get("next") or reverse("compras:agregar")

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


def crear_producto(request):
    return HttpResponse("Crear producto (placeholder)")

def agregar_producto(request):
    return HttpResponse("Crear producto (placeholder)")
def editar_producto(request):
    return HttpResponse("Crear producto (placeholder)")
def eliminar_producto(request):
    return HttpResponse("Crear producto (placeholder)")