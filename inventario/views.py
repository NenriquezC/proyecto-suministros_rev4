"""
Vistas de Inventario: Proveedores y Productos.

Responsabilidades:
- CRUD de Proveedor y Producto (listar/crear/editar/eliminar/ver).
- Endpoints auxiliares (precio de producto en JSON).
- Redirecciones de conveniencia (home de inventario).

Diseño:
- Mantener permisos por acción con @permission_required.
- Reutilizar templates de edición en modo readonly cuando aplica.
- Paginación consistente y filtros básicos para listados.
- No se altera la lógica: solo documentación estandarizada.
"""

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

from django.db.models.deletion import ProtectedError
from django.db import IntegrityError
from django.contrib import messages

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

# ─────────────────────────────────────────────────────────────────────────────
# VISTA: agregar_proveedor
# Propósito: Crear un nuevo proveedor; opcionalmente redirigir a `next`.
# ─────────────────────────────────────────────────────────────────────────────
@login_required
@permission_required("inventario.add_proveedor", raise_exception=True)
def agregar_proveedor(request):
    """
    Crea un proveedor.

    Flujo:
    - GET: muestra formulario vacío.
    - POST: valida y guarda; redirige a `next` si existe o al detalle (readonly).

    Contexto:
    form (ProveedorForm)
    """
    next_url = request.GET.get("next")
    if request.method == "POST":
        form = ProveedorForm(request.POST)
        if form.is_valid():
            proveedor = form.save()
            #messages.success(request, "Proveedor creado correctamente.")
            if next_url:
                for _ in messages.get_messages(request):
                    pass
                return redirect(next_url)
            messages.success(request, "Proveedor creado correctamente.")
            # PARIDAD CON PRODUCTOS: ir a editar
            return redirect("inventario:ver_proveedor", pk=proveedor.pk)
        messages.error(request, "Revisa los errores del formulario.")
    else:
        #👇 Evita que “éxitos” viejos exploten en la pantalla de NUEVO proveedor
        for _ in messages.get_messages(request):
            pass
        form = ProveedorForm()
    return render(
        request,
        "inventario/proveedores/crear_proveedor/crear_proveedor.html",
        {"form": form},
    )


# ─────────────────────────────────────────────────────────────────────────────
# VISTA: editar_proveedor
# Propósito: Editar un proveedor existente (PRG tras éxito).
# ─────────────────────────────────────────────────────────────────────────────
@login_required
@permission_required("inventario.change_proveedor", raise_exception=True)
def editar_proveedor(request, pk):
    """
    Edita un proveedor existente.

    Flujo:
    - GET: carga formulario con instancia.
    - POST: valida, guarda y redirige al detalle readonly (PRG).
    """
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

# ─────────────────────────────────────────────────────────────────────────────
# VISTA: eliminar_proveedor
# Propósito: Confirmación y eliminación de un proveedor.
# ─────────────────────────────────────────────────────────────────────────────
@login_required
@permission_required("inventario.delete_proveedor", raise_exception=True)
def eliminar_proveedor(request, pk):
    """
    Elimina un proveedor previa confirmación.

    Template GET:
    inventario/proveedores/listar_proveedor/eliminar_confirm_proveedor.html
    """
    proveedor = get_object_or_404(Proveedor, pk=pk)

    if request.method == "POST":
        #proveedor.delete()
        # Vacía cualquier mensaje previo para evitar duplicados
        for _ in messages.get_messages(request):
            pass
        try:
            proveedor.delete()
            messages.success(request, "Proveedor eliminado correctamente.")
        except (ProtectedError, IntegrityError):
            messages.error(
                request,
                "No se puede eliminar: hay Productos y/o Compras que lo referencian."
            )
        #messages.success(request, "Proveedor eliminado correctamente.")
        return redirect("inventario:listar_proveedores")

    # ⬇️ Ruta EXACTA según tu estructura actual
    return render(
        request,
        "inventario/proveedores/listar_proveedor/eliminar_confirm_proveedor.html",
        {"proveedor": proveedor},
    )


# ─────────────────────────────────────────────────────────────────────────────
# VISTA: listar_proveedores
# Propósito: Listado paginado de proveedores con filtro `?q=`.
# ─────────────────────────────────────────────────────────────────────────────
@login_required
@permission_required("inventario.view_proveedor", raise_exception=True)
def listar_proveedores(request):
    """
    Lista paginada de proveedores.

    Filtros:
    - q: búsqueda por nombre/email/teléfono.

    Template:
    inventario/proveedores/listar_proveedor/listar_proveedor.html
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


# ─────────────────────────────────────────────────────────────────────────────
# VISTA: ver_proveedor
# Propósito: Ver proveedor en modo solo lectura (reusa template de editar).
# ─────────────────────────────────────────────────────────────────────────────
@login_required
@permission_required("inventario.view_proveedor", raise_exception=True)
def ver_proveedor(request, pk):
    """
    Detalle readonly de Proveedor (reutiliza el template de edición).
    """
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


# ─────────────────────────────────────────────────────────────────────────────
# VISTA: listar_productos (VERSIÓN SIMPLE)
# Propósito: Listado paginado básico de productos (compatibilidad).
# NOTA: Esta definición queda sobrescrita por la versión extendida más abajo.
# ─────────────────────────────────────────────────────────────────────────────
@login_required
@permission_required("inventario.view_producto", raise_exception=True)
def listar_productos(request):
    """
    Versión básica de listar productos (compatibilidad con templates antiguos).
    La versión extendida definida más abajo es la activa en tiempo de ejecución.
    """
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


# ─────────────────────────────────────────────────────────────────────────────
# VISTA: agregar_producto
# Propósito: Crear un nuevo producto; tras guardar redirige a detalle readonly.
# ─────────────────────────────────────────────────────────────────────────────
@login_required
@permission_required("inventario.add_producto", raise_exception=True)
def agregar_producto(request):
    """
    Crea un producto.

    Flujo:
    - GET: formulario vacío.
    - POST: valida y guarda; redirige a ver_producto.
    """
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

# ─────────────────────────────────────────────────────────────────────────────
# VISTA: editar_producto
# Propósito: Editar un producto; PRG y redirección a detalle readonly.
# ─────────────────────────────────────────────────────────────────────────────
@login_required
@permission_required("inventario.change_producto", raise_exception=True)
def editar_producto(request, pk):
    """
    Edita un producto.

    Flujo:
    - GET: formulario con instancia.
    - POST: valida/guarda; redirige a ver_producto.
    """
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


# ─────────────────────────────────────────────────────────────────────────────
# VISTA: eliminar_producto
# Propósito: Confirmación y eliminación de un producto.
# ─────────────────────────────────────────────────────────────────────────────
@login_required
@permission_required("inventario.delete_producto", raise_exception=True)
def eliminar_producto(request, pk):
    """
    Elimina un producto previa confirmación.

    Template GET:
    inventario/productos/listar_producto/eliminar_confirm_lista.html
    """
    prod = get_object_or_404(Producto, pk=pk)
    prod = get_object_or_404(Producto, pk=pk)

    if request.method == "POST":
        # Evitar mensajes duplicados en la cola
        for _ in messages.get_messages(request):
            pass

        try:
            nombre = str(prod)
            prod.delete()
        except (ProtectedError, IntegrityError):
            messages.error(
                request,
                "No se puede eliminar: el producto tiene movimientos (compras/ventas) asociados."
            )
        else:
            messages.success(request, f'Producto  eliminado correctamente.')

        return redirect("inventario:listar_productos")

    return render(
        request,
        "inventario/productos/listar_producto/eliminar_confirm_lista.html",
        {"producto": prod},
    )

# ─────────────────────────────────────────────────────────────────────────────
# VISTA: ver_producto
# Propósito: Detalle readonly del producto (reutiliza template de edición).
# ─────────────────────────────────────────────────────────────────────────────
@login_required
@permission_required("inventario.view_producto", raise_exception=True)
def ver_producto(request, pk):
    """
    Detalle SOLO LECTURA del producto (mismo layout que edición).

    Extras:
    - Calcula margen = precio_venta - precio_compra (Decimal a 2 decimales).
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


# ─────────────────────────────────────────────────────────────────────────────
# VISTA: listar_productos (VERSIÓN EXTENDIDA / ACTIVA)
# Propósito: Listado con filtros (q, categoria, estado) y paginación.
# ─────────────────────────────────────────────────────────────────────────────
@login_required
@permission_required("inventario.view_producto", raise_exception=True)
def listar_productos(request):
    """
    Lista de productos con filtros y paginación.

    Filtros:
    - q: texto en nombre o proveedor.
    - categoria: ID exacto.
    - estado: 'activos' | 'inactivos' | 'reposicion' (stock <= stock_minimo y stock_minimo > 0).

    Contexto adicional:
    - lista_categorias, estado_seleccionado, etc. para partials.
    """
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


# ─────────────────────────────────────────────────────────────────────────────
# API: producto_precio_api (GET)
# Propósito: Devolver precio unitario e info mínima de un producto.
# ─────────────────────────────────────────────────────────────────────────────
@require_GET
def producto_precio_api(request, pk):
    """
    Devuelve info mínima del producto en JSON.

    Respuesta:
    { "id": int, "nombre": str, "precio_unitario": float }

    Notas:
    - Ajusta el atributo de precio según tu modelo (precio_compra/precio_unitario/costo).
    - Devuelve 404 si el producto no existe.
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


# ─────────────────────────────────────────────────────────────────────────────
# VISTA: inventario (home)
# Propósito: Redirigir al listado de proveedores (o productos si lo prefieres).
# ─────────────────────────────────────────────────────────────────────────────
@login_required
def inventario(request):
    """
    Home de inventario: redirige a una vista existente (por defecto, proveedores).
    """
    # Redirige al listado que SÍ existe (Proveedores, ya lo dejamos OK)
    return redirect("inventario:listar_proveedores")
    # Si prefieres ir a productos, cambia por:
    # return redirect("inventario:listar_productos")

    # Alias para compatibilidad con tu URL/plantillas antiguas

# ─────────────────────────────────────────────────────────────────────────────
# ALIAS: proveedor_crear
# Propósito: Mantener compatibilidad con rutas antiguas reusando agregar_proveedor.
# ─────────────────────────────────────────────────────────────────────────────    
@login_required
@permission_required("inventario.add_proveedor", raise_exception=True)
def proveedor_crear(request):
    """
    Alias de `agregar_proveedor` para compatibilidad con rutas/plantillas antiguas.
    """
    # Reusa la lógica de agregar_proveedor para no duplicar código
    return agregar_proveedor(request)