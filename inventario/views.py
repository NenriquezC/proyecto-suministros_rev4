from django.shortcuts import render, redirect         # ✅ Vistas: render templates y redirecciones
from django.urls import reverse                       # ✅ Útil si construyes URLs en código (p.ej. messages+redirect)
from django.contrib import messages                   # ✅ Para flash messages en vistas
from django.contrib.auth.decorators import login_required, permission_required  # ✅ Decoradores en vistas protegidas

from .forms import ProveedorForm                      # ✅ Solo si hay vistas que usen el form de proveedor
from .forms import ProductoForm                       # ✅ Solo si hay vistas que usen el form de producto

from django.http import HttpResponse                  # ❓ Rara vez; puedes quitar si no lo usas
from django.http import JsonResponse, Http404         # ✅ JsonResponse para APIs (ej: precio); Http404 si levantas 404
from django.views.decorators.http import require_GET  # ✅ Si tu endpoint precio usa @require_GET

from .models import Producto, Categoria                         # ✅ Vistas que consultan productos
from django.core.paginator import Paginator           # ✅ Listados con paginación (listar_productos)
from django.db.models import Q, F                     # ✅ Filtros de búsqueda y comparaciones (stock <= stock_minimo)


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

@login_required
@permission_required("inventario.view_producto", raise_exception=True)
def listar_productos(request):
    qs = Producto.objects.select_related("proveedor", "categoria").order_by("nombre")
    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Paso variables amplias para no romper tus templates:
    context = {
        "page_obj": page_obj,
        "object_list": page_obj.object_list,
        "productos": page_obj.object_list,  # por si el template usa este nombre
        "paginator": paginator,
    }
    return render(request, "inventario/productos/listar_producto/lista_producto.html", context)

# Si también tienes estas rutas en urls.py, crea sus placeholders ya:
def listar_proveedores(request):
    return HttpResponse("Listado de proveedores (placeholder)")

def crear_producto(request):
    return HttpResponse("Crear producto (placeholder)")

def agregar_producto(request):
    return HttpResponse("Crear producto (placeholder)")
#---------------------------------------------------------------------------------------------------------------------------
@login_required
@permission_required("inventario.add_producto", raise_exception=True)
def agregar_producto(request):
    if request.method == "POST":
        form = ProductoForm(request.POST)
        if form.is_valid():
            prod = form.save()
            messages.success(request, f'Producto "{prod}" creado correctamente.')
            # Redirige a la lista (si prefieres otra, me dices)
            return redirect(reverse("inventario:listar_productos"))
    else:
        form = ProductoForm()

    return render(
        request,
        "inventario/productos/crear_producto/crear_producto.html",
        {"form": form},
    )
#------------------------------------------------------------------------------------------------------------------------------
@login_required
@permission_required("inventario.change_producto", raise_exception=True)
def editar_producto(request, pk):
    prod = get_object_or_404(Producto, pk=pk)
    if request.method == "POST":
        form = ProductoForm(request.POST, instance=prod)
        if form.is_valid():
            prod = form.save()
            messages.success(request, f'Producto "{prod}" actualizado.')
            return redirect(reverse("inventario:listar_productos"))
    else:
        form = ProductoForm(instance=prod)

    return render(
        request,
        "inventario/productos/editar_producto/editar_producto.html",
        {"form": form, "producto": prod},
    )
#------------------------------------------------------------------------------------------------------------------------------
@login_required
@permission_required("inventario.delete_producto", raise_exception=True)
def eliminar_producto(request, pk):
    prod = get_object_or_404(Producto, pk=pk)
    if request.method == "POST":
        nombre = str(prod)
        prod.delete()
        messages.success(request, f'Producto "{nombre}" eliminado.')
        return redirect(reverse("inventario:listar_productos"))

    # Confirmación (según tu árbol: eliminar_confirm_lista.html)
    return render(
        request,
        "inventario/productos/listar_producto/eliminar_confirm_lista.html",
        {"producto": prod},
    )
#------------------------------------------------------------------------------------------------------------------------------
#Qué cambié y por qué (rápido)
#Filtros: añadí q, categoria, estado para replicar el UX de compras.
#Contexto: agregué productos, pagina_actual, hay_paginacion, lista_categorias, etc., que son los que usan los partials.
#Template: ahora renderiza a inventario/productos/listar_producto.html (el nombre que dijiste).
#Compatibilidad: dejé page_obj, object_list, paginator por si algún template antiguo los usa.
#Con esto, tus partials funcionan tal cual y el badge de reposición aparecerá cuando stock <= stock_minimo.
#En resumen: q = “query” (lo que escribe el usuario para buscar). Es el mismo patrón que usa media internet desde 1998, incluidos buscadores y nuestras tablas 😄.
#------------------------------------------------------------------------------------------------------------------------------

@login_required
@permission_required("inventario.view_producto", raise_exception=True)
def listar_productos(request):
    # Base query
    productos_qs = (
        Producto.objects
        .select_related("proveedor", "categoria")
        .order_by("nombre")
    )

    # --- Filtros ---
    texto_busqueda = request.GET.get("q", "").strip()
    categoria_id = request.GET.get("categoria") or ""
    estado = request.GET.get("estado") or ""

    if texto_busqueda:
        productos_qs = productos_qs.filter(
            Q(nombre__icontains=texto_busqueda) |
            Q(proveedor__nombre__icontains=texto_busqueda)
        )

    if categoria_id:
        productos_qs = productos_qs.filter(categoria_id=categoria_id)

    if estado == "activos":
        productos_qs = productos_qs.filter(activo=True)
    elif estado == "inactivos":
        productos_qs = productos_qs.filter(activo=False)
    elif estado == "reposicion":
        productos_qs = productos_qs.filter(
            stock_minimo__gt=0,
            stock__lte=F("stock_minimo"),
        )

    # --- Paginación ---
    paginator = Paginator(productos_qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    # --- Contexto (compatibilidad + claves para partials) ---
    context = {
        # para tus partials nuevos
        "productos": page_obj.object_list,
        "pagina_actual": page_obj,
        "hay_paginacion": page_obj.has_other_pages(),
        "lista_categorias": Categoria.objects.all().order_by("nombre"),
        "texto_busqueda": texto_busqueda,
        "categoria_id_seleccionada": categoria_id,
        "estado_seleccionado": estado,

        # compat: por si algún template viejo usa estos
        "page_obj": page_obj,
        "object_list": page_obj.object_list,
        "paginator": paginator,
    }

    # Usa el template acordado (no la ruta antigua)
    return render(request, "inventario/productos/listar_producto/lista_producto.html", context)
#------------------------------------------------------------------------------------------------------------------------------
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
