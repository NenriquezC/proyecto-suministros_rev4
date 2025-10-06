from django.shortcuts import render, redirect , get_object_or_404        # ✅ Vistas: render templates y redirecciones
from django.urls import reverse                       # ✅ Útil si construyes URLs en código (p.ej. messages+redirect)
from django.contrib import messages                   # ✅ Para flash messages en vistas
from django.contrib.auth.decorators import login_required, permission_required  # ✅ Decoradores en vistas protegidas

from .forms import ProveedorForm                      # ✅ Solo si hay vistas que usen el form de proveedor
from .forms import ProductoForm                       # ✅ Solo si hay vistas que usen el form de producto

from django.http import HttpResponse                  # ❓ Rara vez; puedes quitar si no lo usas
from django.http import JsonResponse, Http404         # ✅ JsonResponse para APIs (ej: precio); Http404 si levantas 404
from django.views.decorators.http import require_GET  # ✅ Si tu endpoint precio usa @require_GET

from .models import Producto, Categoria, Proveedor                         # ✅ Vistas que consultan productos
from django.core.paginator import Paginator           # ✅ Listados con paginación (listar_productos)
from django.db.models import Q, F                     # ✅ Filtros de búsqueda y comparaciones (stock <= stock_minimo)
from decimal import Decimal

"""@login_required
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
    )"""

# --- CREAR ---
@login_required
@permission_required("inventario.add_proveedor", raise_exception=True)
def agregar_proveedor(request):
    next_url = request.GET.get("next")
    if request.method == "POST":
        form = ProveedorForm(request.POST)
        if form.is_valid():
            proveedor = form.save()
            messages.success(request, "Proveedor creado correctamente.")
            if next_url:
                return redirect(next_url)
            # PARIDAD CON PRODUCTOS: ir a editar
            return redirect("inventario:ver_proveedor", pk=proveedor.pk)
        messages.error(request, "Revisa los errores del formulario.")
    else:
        form = ProveedorForm()
    return render(
        request,
        "inventario/proveedores/crear_proveedor/crear_proveedor.html",
        {"form": form},
    )


# --- EDITAR ---
@login_required
@permission_required("inventario.change_proveedor", raise_exception=True)
def editar_proveedor(request, pk):
    proveedor = get_object_or_404(Proveedor, pk=pk)
    if request.method == "POST":
        form = ProveedorForm(request.POST, instance=proveedor)
        if form.is_valid():
            form.save()
            messages.success(request, "Proveedor actualizado correctamente.")
            # PARIDAD CON PRODUCTOS: quedarse en editar (PRG)
            return redirect("inventario:ver_proveedor", pk=proveedor.pk)
        messages.error(request, "Revisa los errores del formulario.")
    else:
        form = ProveedorForm(instance=proveedor)
    return render(
        request,
        "inventario/proveedores/editar_proveedor/editar_proveedor.html",
        {"form": form, "proveedor": proveedor},
    )

# --- ELIMINAR (confirmación en listar_proveedor) ---
@login_required
@permission_required("inventario.delete_proveedor", raise_exception=True)
def eliminar_proveedor(request, pk):
    """
    Confirmación y borrado.
    Template (GET): templates/inventario/proveedores/listar_proveedor/eliminar_confirm_proveedor.html
    """
    proveedor = get_object_or_404(Proveedor, pk=pk)

    if request.method == "POST":
        proveedor.delete()
        messages.success(request, "Proveedor eliminado correctamente.")
        return redirect("inventario:listar_proveedores")

    # ⬇️ Ruta EXACTA según tu estructura actual
    return render(
        request,
        "inventario/proveedores/listar_proveedor/eliminar_confirm_proveedor.html",
        {"proveedor": proveedor},
    )


# --- LISTAR ---
@login_required
@permission_required("inventario.view_proveedor", raise_exception=True)
def listar_proveedores(request):
    """
    Lista paginada de proveedores.
    Template: templates/inventario/proveedores/listar_proveedor/listar_proveedor.html
    """
    queryset = Proveedor.objects.all().order_by("-id")

    # Filtro simple opcional por ?q=
    q = request.GET.get("q")
    if q:
        # Ajusta campos si tus nombres reales difieren
        queryset = queryset.filter(
            Q(nombre__icontains=q) | Q(email__icontains=q) | Q(telefono__icontains=q)
        )

    paginator = Paginator(queryset, 10)
    page = request.GET.get("page")
    proveedores = paginator.get_page(page)

    return render(
        request,
        "inventario/proveedores/listar_proveedor/listar_proveedor.html",
        {"proveedores": proveedores},
    )


@login_required
@permission_required("inventario.view_proveedor", raise_exception=True)
def ver_proveedor(request, pk):
    proveedor = get_object_or_404(Proveedor, pk=pk)

    # Reusar el mismo template de EDITAR con el form deshabilitado
    form = ProveedorForm(instance=proveedor)
    for f in form.fields.values():
        f.disabled = True

    return render(
        request,
        "inventario/proveedores/editar_proveedor/editar_proveedor.html",
        {
            "proveedor": proveedor,
            "form": form,
            "readonly": True,  # EXACTAMENTE como en ver_producto
        },
    )

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
            #return redirect(reverse("inventario:listar_productos"))
            return redirect("inventario:ver_producto", pk=prod.pk)  # ← ver detalle readonly
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
            messages.success(request, f'Producto "{prod}" Editado exitosamente') #mensaje de edicion exitosa
            return redirect("inventario:ver_producto", pk = prod.pk)
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
##------------------------------------------------------------------------------------------------------------------------------
@login_required
@permission_required("inventario.view_producto", raise_exception=True)
def ver_producto(request, pk):
    """
    Detalle SOLO LECTURA del producto.
    Mantiene el mismo patrón visual que Compras (readonly).
    """
    producto = get_object_or_404(Producto, pk=pk)

    # Reusar un form deshabilitado mantiene estilos/partials si los usas
    form = ProductoForm(instance=producto)
    for f in form.fields.values():
        f.disabled = True

    # Margen en dinero = precio_venta - precio_compra
    margen = (producto.precio_venta - producto.precio_compra).quantize(Decimal("0.01"))

    return render(
        request,
        "inventario/productos/editar_producto/editar_producto.html",
        {
            "producto": producto,
            "form": form,
            "readonly": True,   # bandera de UI (igual que en compras)
            "margen": margen,
        },
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



@login_required
def inventario(request):
    # Redirige al listado que SÍ existe (Proveedores, ya lo dejamos OK)
    return redirect("inventario:listar_proveedores")
    # Si prefieres ir a productos, cambia por:
    # return redirect("inventario:listar_productos")

    # Alias para compatibilidad con tu URL/plantillas antiguas
@login_required
@permission_required("inventario.add_proveedor", raise_exception=True)
def proveedor_crear(request):
    # Reusa la lógica de agregar_proveedor para no duplicar código
    return agregar_proveedor(request)