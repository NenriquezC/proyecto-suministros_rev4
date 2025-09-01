# compras/views.py (ejemplo)
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from .forms import CompraForm, CompraProductoFormSet
from .models import Compra
from .services import calcular_y_guardar_totales_compra  # el servicio que te pasé
from django.core.paginator import Paginator
from django.db.models import Q
from inventario.models import Proveedor
from django.contrib import messages 


@transaction.atomic
def crear_compra(request):
    if request.method == "POST":
        form = CompraForm(request.POST)
        if form.is_valid():
            compra = form.save(commit=False)
            compra.usuario = request.user  # si corresponde
            compra.save()
            formset = CompraProductoFormSet(request.POST, instance=compra)
            if formset.is_valid():
                formset.save()
                calcular_y_guardar_totales_compra(compra)  
                return redirect("compras:detalle", pk=compra.pk)
        else:
            compra = Compra()
            formset = CompraProductoFormSet(request.POST, instance=compra)
    else:
        form = CompraForm()
        formset = CompraProductoFormSet()
    
    return render(request, "compras/agregar_compra.html", {"form": form, "formset": formset})

def ver_compras(request):
    # Consulta base: todas las compras con su proveedor
    compras_queryset = Compra.objects.select_related('proveedor').order_by('-fecha', '-id')

    # --- Filtros de búsqueda ---
    texto_busqueda = request.GET.get('q', '').strip()
    fecha_desde = request.GET.get('desde')  # formato 'YYYY-MM-DD'
    fecha_hasta = request.GET.get('hasta')  # formato 'YYYY-MM-DD'
    proveedor_id_seleccionado = request.GET.get('proveedor')

    # Aplicar búsqueda por ID de compra o nombre de proveedor
    if texto_busqueda:
        compras_queryset = compras_queryset.filter(
            Q(id__icontains=texto_busqueda) | Q(proveedor__nombre__icontains=texto_busqueda)
        )

    # Filtrar por rango de fechas
    if fecha_desde:
        compras_queryset = compras_queryset.filter(fecha__date__gte=fecha_desde)
    if fecha_hasta:
        compras_queryset = compras_queryset.filter(fecha__date__lte=fecha_hasta)

    # Filtrar por proveedor específico
    if proveedor_id_seleccionado:
        compras_queryset = compras_queryset.filter(proveedor_id=proveedor_id_seleccionado)

    # --- Paginación ---
    paginador = Paginator(compras_queryset, 20)  # 20 compras por página
    numero_pagina = request.GET.get('page')
    pagina_actual = paginador.get_page(numero_pagina)

    contexto = {
        'compras': pagina_actual.object_list,
        'pagina_actual': pagina_actual,
        'hay_paginacion': pagina_actual.has_other_pages(),
        # Para llenar el <select> de proveedores en el template
        'lista_proveedores': Proveedor.objects.all().order_by('nombre'),
        # Para preservar los filtros en la UI
        'texto_busqueda': texto_busqueda,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'proveedor_id_seleccionado': proveedor_id_seleccionado,
    }
    return render(request, 'compras/lista.html', contexto)

def detalle_compra(request, pk):
    compra_encontrada = get_object_or_404(Compra.objects.select_related('proveedor'), pk=pk)
    return render(request, 'compras/detalle.html', {'compra': compra_encontrada})

@transaction.atomic
def editar_compra(request, pk):
    compra_objetivo = get_object_or_404(Compra, pk=pk)

    # Estado previo de líneas para reconciliar stock
    estado_previo_lineas = {l.pk: (l.producto_id, l.cantidad) for l in compra_objetivo.lineas.all()}

    if request.method == 'POST':
        formulario_compra = CompraForm(request.POST, instance=compra_objetivo)
        formulario_detalle_compra = CompraProductoFormSet(request.POST, instance=compra_objetivo)
        if formulario_compra.is_valid() and formulario_detalle_compra.is_valid():
            formulario_compra.save()
            formulario_detalle_compra.save()

            from . import services
            services.reconciliar_stock_tras_editar_compra(compra_objetivo, estado_previo_lineas)
            services.calcular_y_guardar_totales_compra(compra_objetivo, tasa_impuesto_pct=None)

            messages.success(request, "Compra actualizada correctamente.")
            return redirect('compras:detalle', pk=compra_objetivo.pk)
    else:
        formulario_compra = CompraForm(instance=compra_objetivo)
        formulario_detalle_compra = CompraProductoFormSet(instance=compra_objetivo)

    contexto = {
        'compra': compra_objetivo,
        'formulario_compra': formulario_compra,
        'formulario_detalle_compra': formulario_detalle_compra,
    }
    return render(request, 'compras/form.html', contexto)

@transaction.atomic
def eliminar_compra(request, pk):
    compra_objetivo = get_object_or_404(Compra, pk=pk)
    if request.method == 'POST':
        # (Opcional) crear un service para revertir stock antes de borrar, si lo decides
        compra_objetivo.delete()
        messages.success(request, "Compra eliminada.")
        return redirect('compras:ver_compras')
    return render(request, 'compras/eliminar_confirm.html', {'compra': compra_objetivo})

def detalle_compra(request, pk):
    compra_encontrada = get_object_or_404(Compra.objects.select_related('proveedor'), pk=pk)
    return render(request, 'compras/detalle.html', {'compra': compra_encontrada})

@transaction.atomic
def editar_compra(request, pk):
    compra_objetivo = get_object_or_404(Compra, pk=pk)
    if request.method == 'POST':
        formulario_compra = CompraForm(request.POST, instance=compra_objetivo)
        formulario_detalle_compra = CompraProductoFormSet(request.POST, instance=compra_objetivo)
        if formulario_compra.is_valid() and formulario_detalle_compra.is_valid():
            formulario_compra.save()
            formulario_detalle_compra.save()
            from . import services
            estado_previo_lineas = {l.pk: (l.producto_id, l.cantidad) for l in compra_objetivo.lineas.all()}
            services.reconciliar_stock_tras_editar_compra(compra_objetivo, estado_previo_lineas)
            services.calcular_y_guardar_totales_compra(compra_objetivo, tasa_impuesto_pct=None)
            messages.success(request, "Compra actualizada.")
            return redirect('compras:detalle', pk=compra_objetivo.pk)
    else:
        formulario_compra = CompraForm(instance=compra_objetivo)
        formulario_detalle_compra = CompraProductoFormSet(instance=compra_objetivo)

    return render(request, 'compras/form.html', {
        'compra': compra_objetivo,
        'formulario_compra': formulario_compra,
        'formulario_detalle_compra': formulario_detalle_compra,
    })

@transaction.atomic
def eliminar_compra(request, pk):
    compra_objetivo = get_object_or_404(Compra, pk=pk)
    if request.method == 'POST':
        compra_objetivo.delete()
        messages.success(request, "Compra eliminada.")
        return redirect('compras:ver_compras')
    return render(request, 'compras/eliminar_confirm.html', {'compra': compra_objetivo})



# al final de compras/views.py
agregar_compra = crear_compra