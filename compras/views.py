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
from django.contrib.auth.decorators import login_required
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
@login_required
@transaction.atomic
def crear_compra(request):
    FORMS_PREFIX = "lineas"

    if request.method == "POST":
        data = request.POST.copy()
        if data.get("descuento_total") in (None, ""):
            data["descuento_total"] = "0"

        form = CompraForm(data)
        if form.is_valid():
            compra = form.save(commit=False)

            # usuario es NOT NULL → set explícito antes del save
            compra.usuario_id = request.user.pk
            compra.save()

            formset = CompraProductoFormSet(data, instance=compra, prefix=FORMS_PREFIX)
            if formset.is_valid():
                formset.save()

                # DEBUG: cuántas líneas quedaron realmente
                print("DEBUG >>> líneas guardadas:", compra.lineas.count())
                print("DEBUG >>> detalle:", list(compra.lineas.values_list("producto_id","cantidad","precio_unitario")))

                try:
                    services.calcular_y_guardar_totales_compra(compra)
                except Exception:
                    pass

                messages.success(request, "Compra creada correctamente.")
                return redirect("compras:detalle", pk=compra.pk)
            else:
                print("DEBUG >>> formset.errors:", [f.errors for f in formset.forms], formset.non_form_errors())
                compra.delete()
        else:
            formset = CompraProductoFormSet(data, instance=Compra(), prefix=FORMS_PREFIX)
    else:
        form = CompraForm()
        formset = CompraProductoFormSet(instance=Compra(), prefix=FORMS_PREFIX)

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
    compra = get_object_or_404(Compra, pk=pk)
    estado_previo_lineas = {l.pk: (l.producto_id, l.cantidad) for l in compra.lineas.all()}

    if request.method == "POST":
        data = request.POST.copy()
        if data.get("descuento_total") in (None, ""):
            data["descuento_total"] = "0"

        form = CompraForm(data, instance=compra)
        formset = CompraProductoFormSet(data, instance=compra, prefix="lineas")

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

        # DEBUG por si algo persiste
        print("EDIT DEBUG form.errors:", form.errors)
        print("EDIT DEBUG formset non-form:", formset.non_form_errors())
        print("EDIT DEBUG formset per-form:", [f.errors for f in formset.forms])

    else:
        form = CompraForm(instance=compra)
        formset = CompraProductoFormSet(instance=compra, prefix="lineas")

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