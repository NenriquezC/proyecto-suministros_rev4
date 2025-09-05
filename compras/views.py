# compras/views.py
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

    # NUEVA plantilla en carpeta editar_compra/ (usa 'form' y 'formset')
    return render(
        request,
        "compras/editar_compra/editar_compra.html",
        {"form": form, "formset": formset, "compra": compra},
    )


# ─────────────────────────────────────────────────────────────────────────────
# LISTAR / GESTIÓN
# ─────────────────────────────────────────────────────────────────────────────
def ver_compras(request):
    compras_queryset = Compra.objects.select_related("proveedor").order_by("-fecha", "-id")

    # filtros
    texto_busqueda = request.GET.get("q", "").strip()
    fecha_desde = request.GET.get("desde")
    fecha_hasta = request.GET.get("hasta")
    proveedor_id = request.GET.get("proveedor")

    if texto_busqueda:
        compras_queryset = compras_queryset.filter(
            Q(id__icontains=texto_busqueda) |
            Q(proveedor__nombre__icontains=texto_busqueda)
        )
    if fecha_desde:
        compras_queryset = compras_queryset.filter(fecha__date__gte=fecha_desde)
    if fecha_hasta:
        compras_queryset = compras_queryset.filter(fecha__date__lte=fecha_hasta)
    if proveedor_id:
        compras_queryset = compras_queryset.filter(proveedor_id=proveedor_id)

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
    # Usa el template que ya tienes para esta pantalla:
    # - Si tu listado está en 'compras/lista.html', deja esta línea:
    #return render(request, "compras/lista.html", contexto)
    return render(request,"compras/lista_compra/lista.html", contexto)
    # - Si prefieres 'compras/ver_compras.html', cambia SOLO la línea anterior
    #   por: return render(request, "compras/ver_compras.html", contexto)

# ─────────────────────────────────────────────────────────────────────────────
# LISTAR SOLO LECTURA ES EL CODIGO DEL OJO, PARA VER
# ─────────────────────────────────────────────────────────────────────────────

def ver_compra(request, pk):
    # NADA de POST acá: esta vista es solo lectura
    compra = get_object_or_404(Compra.objects.select_related("proveedor"), pk=pk)

    # Reusar los mismos forms que en "editar", pero deshabilitados
    form = CompraForm(instance=compra)
    for field in form.fields.values():
        field.disabled = True

    formset = CompraProductoFormSet(instance=compra)
    for f in formset.forms:
        for field in f.fields.values():
            field.disabled = True

    contexto = {
        "form": form,
        "formset": formset,
        "compra": compra,
        "readonly": True,  # bandera para la plantilla
    }
    return render(request, "compras/editar_compra/editar_compra.html", contexto)
# ─────────────────────────────────────────────────────────────────────────────
# DETALLE
# ─────────────────────────────────────────────────────────────────────────────
#ESTE ES EL DETALLE COMPRA QUE ESTABA ANTES DEL READONLY PARA EL CODIGO DEL OJO(VER)
#def detalle_compra(request, pk):
#    compra = get_object_or_404(Compra.objects.select_related("proveedor"), pk=pk)
#    return render(request, "compras/detalle.html", {"compra": compra})
def detalle_compra(request, pk):
    compra = get_object_or_404(Compra.objects.select_related("proveedor"), pk=pk)

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
    ctx = {"compra": compra, "form": form, "formset": formset, "readonly": True}
    return render(request, "compras/editar_compra/editar_compra.html", ctx)

# ─────────────────────────────────────────────────────────────────────────────
# ELIMINAR (CONFIRMAR + POST)
# ─────────────────────────────────────────────────────────────────────────────
@transaction.atomic
def eliminar_compra(request, pk):
    compra = get_object_or_404(Compra, pk=pk)
    if request.method == "POST":
        # si necesitas revertir stock, llama a un service aquí antes del delete
        compra.delete()
        messages.success(request, "Compra eliminada.")
        return redirect("compras:ver_compras")
    return render(request, "compras/eliminar_confirm.html", {"compra": compra})


# Alias opcional por si en algún template quedó 'compras:agregar_compra'
agregar_compra = crear_compra