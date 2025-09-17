# compras/views.py
"""
Vistas de la app 'compras'.

Incluye flujos CRUD (crear, editar, ver detalle/solo lectura, listar y eliminar)
para el modelo Compra y su formset de líneas. Las vistas críticas se decoran con
transacciones atómicas para asegurar consistencia entre cabecera y líneas.

Dependencias:
- forms.CompraForm y forms.CompraProductoFormSet
- models.Compra
- services: utilidades de negocio (reconciliar stock, calcular totales)
- inventario.models.Proveedor: para filtros y listados
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q

from .forms import CompraForm, CompraProductoFormSet
from .models import Compra
from . import services  # para reconciliar stock y calcular totales
from inventario.models import Proveedor


# ─────────────────────────────────────────────────────────────────────────────
# CREAR
# ─────────────────────────────────────────────────────────────────────────────
@transaction.atomic
def crear_compra(request):
    """
    Crea una nueva Compra y sus líneas via form + formset.

    POST:
    - Valida CompraForm y CompraProductoFormSet.
    - Asigna usuario si aplica.
    - Persiste compra y líneas en una transacción atómica.
    - Calcula totales mediante services.
    - Redirige al detalle al éxito.

    GET:
    - Entrega formularios vacíos.

    Returns:
        HttpResponse con la plantilla 'compras/agregar_compra/agregar_compra.html'
        y el contexto {'form', 'formset'} en GET/errores; Redirect en éxito.

    Side effects:
        - Mensajes flash (messages.success).
        - Escritura en DB (Compra + líneas).
        - Cálculo de totales (services).
    """
    if request.method == "POST":
        form = CompraForm(request.POST)
        if form.is_valid():
            compra = form.save(commit=False)
            # si tu modelo tiene usuario:
            if hasattr(compra, "usuario") and request.user.is_authenticated:
                compra.usuario = request.user
            compra.save()

            formset = CompraProductoFormSet(request.POST, instance=compra)
            if formset.is_valid():
                formset.save()
                try:
                    services.calcular_y_guardar_totales_compra(compra)
                except Exception:
                    pass
                messages.success(request, "Compra creada correctamente.")
                return redirect("compras:detalle", pk=compra.pk)
        else:
            # si el form es inválido, usa una instancia temporal para mantener el formset
            compra = Compra()
            formset = CompraProductoFormSet(request.POST, instance=compra)
    else:
        form = CompraForm()
        formset = CompraProductoFormSet()

    # NUEVA plantilla en carpeta agregar_compra/
    return render(
        request,
        "compras/agregar_compra/agregar_compra.html",
        {"form": form, "formset": formset},
    )


# ─────────────────────────────────────────────────────────────────────────────
# EDITAR
# ─────────────────────────────────────────────────────────────────────────────
@transaction.atomic
def editar_compra(request, pk):
    """
    Edita una Compra existente y sus líneas de forma atómica.

    Args:
        pk (int): Identificador de la Compra.

    Flujo:
        - Carga estado previo de líneas (producto_id, cantidad) para reconciliar stock.
        - En POST, valida y guarda form + formset.
        - Llama services.reconciliar_stock_tras_editar_compra para ajustar inventario.
        - Recalcula totales.

    Returns:
        HttpResponse de 'compras/editar_compra/editar_compra.html' con
        {'compra', 'form', 'formset', 'readonly': False} o Redirect en éxito.
    """
    compra = get_object_or_404(Compra, pk=pk)

    # estado previo para reconciliar stock
    estado_previo_lineas = {l.pk: (l.producto_id, l.cantidad) for l in compra.lineas.all()}

    if request.method == "POST":
        form = CompraForm(request.POST, instance=compra)
        formset = CompraProductoFormSet(request.POST, instance=compra)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()

            try:
                services.reconciliar_stock_tras_editar_compra(compra, estado_previo_lineas)
            except Exception:
                pass
            try:
                services.calcular_y_guardar_totales_compra(compra, tasa_impuesto_pct=None)
            except Exception:
                pass

            messages.success(request, "Compra actualizada correctamente.")
            return redirect("compras:detalle", pk=compra.pk)
    else:
        form = CompraForm(instance=compra)
        formset = CompraProductoFormSet(instance=compra)



    return render(
        request,
        "compras/editar_compra/editar_compra.html",
        {"compra": compra, "form": form, "formset": formset, "readonly": False},
    )

    # NUEVA plantilla en carpeta editar_compra/ (usa 'form' y 'formset')
    #return render(
    #    request,
    #    "compras/editar_compra/editar_compra.html",
    #    {"form": form, "formset": formset, "compra": compra},
    #)


# ─────────────────────────────────────────────────────────────────────────────
# LISTAR / GESTIÓN
# ─────────────────────────────────────────────────────────────────────────────
def ver_compras(request):
    """
    Lista paginada de Compras con filtros básicos.

    Filtros GET:
        q        : búsqueda por id (icontains) o proveedor.nombre (icontains)
        desde    : fecha mínima (YYYY-MM-DD)
        hasta    : fecha máxima (YYYY-MM-DD)
        proveedor: id de proveedor

    Returns:
        HttpResponse con la plantilla de listado y contexto:
        {
            'compras', 'pagina_actual', 'hay_paginacion', 'lista_proveedores',
            'texto_busqueda', 'fecha_desde', 'fecha_hasta', 'proveedor_id_seleccionado'
        }

    Notas:
        - select_related("proveedor") para evitar N+1 en la tabla.
        - Orden por fecha DESC y id DESC para estabilidad.
    """
    compras_queryset = Compra.objects.select_related("proveedor").order_by("-fecha", "-id")

    # filtros
    texto_busqueda = request.GET.get("q", "").strip()
    fecha_desde = request.GET.get("desde")
    fecha_hasta = request.GET.get("hasta")
    proveedor_id = request.GET.get("proveedor")
    # Búsqueda por texto libre.
    if texto_busqueda:
        compras_queryset = compras_queryset.filter(
            Q(id__icontains=texto_busqueda) |
            Q(proveedor__nombre__icontains=texto_busqueda)
        )
    # Rango de fechas (notar __date para truncar datetime).
    if fecha_desde:
        compras_queryset = compras_queryset.filter(fecha__date__gte=fecha_desde)
    if fecha_hasta:
        compras_queryset = compras_queryset.filter(fecha__date__lte=fecha_hasta)
    # Filtro por proveedor
    if proveedor_id:
        compras_queryset = compras_queryset.filter(proveedor_id=proveedor_id)
    # Paginación (20 por página; ajustar según UI/UX).
    paginador = Paginator(compras_queryset, 20)
    pagina = paginador.get_page(request.GET.get("page"))

    contexto = {
        "compras": pagina.object_list,
        "pagina_actual": pagina,
        "hay_paginacion": pagina.has_other_pages(),
        "lista_proveedores": Proveedor.objects.all().order_by("nombre"),
        "texto_busqueda": texto_busqueda,
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "proveedor_id_seleccionado": proveedor_id,
    }
    # Mantener el template de listado consensuado.
    # return render(request, "compras/lista.html", contexto)
    return render(request,"compras/lista_compra/lista.html", contexto)
    

# ─────────────────────────────────────────────────────────────────────────────
# LISTAR SOLO LECTURA ES EL CODIGO DEL OJO, PARA VER
# ─────────────────────────────────────────────────────────────────────────────

def ver_compra(request, pk):
    """
    Vista SOLO lectura (UI de editar, pero todo disabled).
    Útil para “ojo”/detalle sin riesgo de modificación.

    Args:
        pk (int): Identificador de Compra.

    Returns:
        HttpResponse usando 'compras/editar_compra/editar_compra.html' con
        {'form', 'formset', 'compra', 'readonly': True}.
    """
    # NADA de POST acá: esta vista es solo lectura
    compra = get_object_or_404(Compra.objects.select_related("proveedor"), pk=pk)

    # Deshabilitar campos del form principal
    form = CompraForm(instance=compra)
    for field in form.fields.values():
        field.disabled = True
    # Deshabilitar campos del formset
    formset = CompraProductoFormSet(instance=compra)
    for f in formset.forms:
        for field in f.fields.values():
            field.disabled = True

    contexto = {
        "form": form,
        "formset": formset,
        "compra": compra,
        "readonly": True,   # bandera de UI para ocultar acciones/JS de edición
    }
    return render(request, "compras/editar_compra/editar_compra.html", contexto)
# ─────────────────────────────────────────────────────────────────────────────
# DETALLE (SOLO LECTURA, MISMA PLANTILLA)
# ─────────────────────────────────────────────────────────────────────────────
#ESTE ES EL DETALLE COMPRA QUE ESTABA ANTES DEL READONLY PARA EL CODIGO DEL OJO(VER)
#def detalle_compra(request, pk):
#    compra = get_object_or_404(Compra.objects.select_related("proveedor"), pk=pk)
#    return render(request, "compras/detalle.html", {"compra": compra})
def detalle_compra(request, pk):
    """
    Detalle de Compra en modo solo lectura, reusando la plantilla de edición.
    (Equivalente a ver_compra; se mantiene por compatibilidad semántica/URLs)

    Args:
        pk (int): Identificador de Compra.

    Returns:
        HttpResponse con la plantilla 'compras/editar_compra/editar_compra.html'
        y {'compra', 'form', 'formset', 'readonly': True}.
    """
    
    compra = get_object_or_404(Compra, pk=pk)


    # Form de cabecera deshabilitado
    form = CompraForm(instance=compra)
    for f in form.fields.values():
        f.disabled = True

    # Formset de líneas deshabilitado
    formset = CompraProductoFormSet(instance=compra)
    for frm in formset.forms:
        for f in frm.fields.values():
            f.disabled = True
    formset.can_delete = False  # por si tu template lo mira

    # Bandera para ocultar botones/JS de edición en los parciales
    return render(
        request,
        "compras/editar_compra/editar_compra.html",
        {"compra": compra, "form": form, "formset": formset, "readonly": True},
    )

# ─────────────────────────────────────────────────────────────────────────────
# ELIMINAR (CONFIRMAR + POST)
# ─────────────────────────────────────────────────────────────────────────────
@transaction.atomic
def eliminar_compra(request, pk):
    """
    Elimina una Compra previa confirmación.

    Args:
        pk (int): Identificador de Compra.

    POST:
        - Elimina la compra (y cascada según on_delete configurado).
        - Envía mensaje de éxito y redirige al listado.

    GET:
        - Muestra pantalla de confirmación.

    Returns:
        HttpResponse (confirmación) o Redirect (éxito).
    """
    compra = get_object_or_404(Compra, pk=pk)
    if request.method == "POST":
        # Si manejas inventario, considera reconciliar stock previo al delete:
        # services.revertir_stock_por_eliminacion(compra)
        compra.delete()
        messages.success(request, "Compra eliminada.")
        return redirect("compras:ver_compras")
    return render(request, "compras/eliminar_confirm.html", {"compra": compra})


# Alias opcional por compatibilidad con rutas antiguas
agregar_compra = crear_compra