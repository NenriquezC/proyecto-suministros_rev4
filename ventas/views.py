# ventas/views.py
"""
Vistas de la app 'ventas'.

Clona el flujo de 'compras' pero usando Venta/VentaProducto y sus plantillas
equivalentes en la app 'ventas'.

Requiere:
- forms.VentaForm y forms.VentaProductoFormSet
- models.Venta
- (opcional) services: utilidades negocio (recalcular totales, reconciliar stock)
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib.auth import get_user_model

from .forms import VentaForm, VentaProductoFormSet
from .models import Venta
try:
    # si tienes un services.py en ventas, lo importamos con alias
    from . import services as services_ventas
except Exception:  # pragma: no cover
    services_ventas = None

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# CREAR
# ─────────────────────────────────────────────────────────────────────────────
@login_required
@transaction.atomic
def crear_venta(request):
    FORMS_PREFIX = "lineas"

    if request.method == "POST":
        data = request.POST.copy()
        # normaliza descuento_total vacío a 0
        if data.get("descuento_total") in (None, ""):
            data["descuento_total"] = "0"

        form = VentaForm(data)
        if form.is_valid():
            venta = form.save(commit=False)
            # si quieres guardar el usuario operador:
            # venta.usuario_id = request.user.pk  # solo si existe campo
            venta.save()

            formset = VentaProductoFormSet(data, instance=venta, prefix=FORMS_PREFIX)
            if formset.is_valid():
                formset.save()

                # Recalcular totales si tienes services
                if services_ventas:
                    try:
                        services_ventas.calcular_y_guardar_totales_venta(venta)
                    except Exception:
                        pass

                messages.success(request, "Venta creada correctamente.")
                return redirect("ventas:detalle", pk=venta.pk)
            else:
                # si las líneas fallan, deshacemos la cabecera creada
                venta.delete()
        else:
            # form inválido → render con formset “vacío” para no romper template
            formset = VentaProductoFormSet(data, instance=Venta(), prefix=FORMS_PREFIX)
    else:
        form = VentaForm()
        formset = VentaProductoFormSet(instance=Venta(), prefix=FORMS_PREFIX)

    return render(
        request,
        "ventas/agregar_venta/agregar_venta.html",
        {"form": form, "formset": formset},
    )


# Alias por consistencia con compras
agregar_venta = crear_venta


# ─────────────────────────────────────────────────────────────────────────────
# EDITAR
# ─────────────────────────────────────────────────────────────────────────────
@login_required
@transaction.atomic
def editar_venta(request, pk):
    venta = get_object_or_404(Venta, pk=pk)

    # Si necesitas reconciliar stock al editar, captura estado previo de líneas:
    estado_previo = {l.pk: (l.producto_id, l.cantidad) for l in venta.detalles.all()}

    if request.method == "POST":
        data = request.POST.copy()
        if data.get("descuento_total") in (None, ""):
            data["descuento_total"] = "0"

        form = VentaForm(data, instance=venta)
        formset = VentaProductoFormSet(data, instance=venta, prefix="lineas")

        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()

            # reconciliar y recalcular si hay services
            if services_ventas:
                try:
                    services_ventas.reconciliar_stock_tras_editar_venta(venta, estado_previo)
                except Exception:
                    pass
                try:
                    services_ventas.calcular_y_guardar_totales_venta(venta, tasa_impuesto_pct=None)
                except Exception:
                    pass

            messages.success(request, "Venta actualizada correctamente.")
            return redirect("ventas:detalle", pk=venta.pk)
    else:
        form = VentaForm(instance=venta)
        formset = VentaProductoFormSet(instance=venta, prefix="lineas")

    return render(
        request,
        "ventas/editar_venta/editar_venta.html",
        {"venta": venta, "form": form, "formset": formset, "readonly": False},
    )


# ─────────────────────────────────────────────────────────────────────────────
# LISTAR
# ─────────────────────────────────────────────────────────────────────────────
@login_required
def ver_ventas(request):
    """
    Lista paginada de Ventas con filtros básicos (clon de ver_compras).
    Filtros GET:
        q       : búsqueda por id (icontains) o cliente.username (icontains)
        desde   : fecha mínima (YYYY-MM-DD)
        hasta   : fecha máxima (YYYY-MM-DD)
        cliente : id del usuario cliente
    """
    ventas_qs = Venta.objects.select_related("cliente").order_by("-fecha", "-id")

    texto_busqueda = request.GET.get("q", "").strip()
    fecha_desde = request.GET.get("desde")
    fecha_hasta = request.GET.get("hasta")
    cliente_id = request.GET.get("cliente")

    if texto_busqueda:
        ventas_qs = ventas_qs.filter(
            Q(id__icontains=texto_busqueda) |
            Q(cliente__username__icontains=texto_busqueda)
        )

    if fecha_desde:
        ventas_qs = ventas_qs.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        ventas_qs = ventas_qs.filter(fecha__lte=fecha_hasta)

    if cliente_id:
        ventas_qs = ventas_qs.filter(cliente_id=cliente_id)

    paginator = Paginator(ventas_qs, 20)
    pagina = paginator.get_page(request.GET.get("page"))

    contexto = {
        "ventas": pagina.object_list,
        "pagina_actual": pagina,
        "hay_paginacion": pagina.has_other_pages(),
        "lista_clientes": User.objects.all().order_by("username"),
        "texto_busqueda": texto_busqueda,
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "cliente_id_seleccionado": cliente_id,
    }
    # Según tu árbol: en ventas el archivo se llama listar_venta.html
    return render(request, "ventas/lista_venta/lista_venta.html", contexto)


# ─────────────────────────────────────────────────────────────────────────────
# VER (SOLO LECTURA) – “ojo”
# ─────────────────────────────────────────────────────────────────────────────
@login_required
def ver_venta(request, pk):
    venta = get_object_or_404(Venta.objects.select_related("cliente"), pk=pk)

    form = VentaForm(instance=venta)
    for f in form.fields.values():
        f.disabled = True

    formset = VentaProductoFormSet(instance=venta)
    for frm in formset.forms:
        for f in frm.fields.values():
            f.disabled = True
    formset.can_delete = False

    contexto = {
        "form": form,
        "formset": formset,
        "venta": venta,
        "readonly": True,
    }
    # Reutilizamos la misma plantilla de edición en modo readonly (como compras)
    return render(request, "ventas/editar_venta/editar_venta.html", contexto)


# Alias semántico (compatibilidad), mismo comportamiento que ver_venta
detalle = ver_venta
detalle_venta = ver_venta


# ─────────────────────────────────────────────────────────────────────────────
# ELIMINAR (confirmación + POST)
# ─────────────────────────────────────────────────────────────────────────────
@login_required
@transaction.atomic
def eliminar_venta(request, pk):
    venta = get_object_or_404(Venta, pk=pk)
    if request.method == "POST":
        # Si manejas inventario, considera revertir stock aquí antes de borrar.
        venta.delete()
        messages.success(request, "Venta eliminada.")
        return redirect("ventas:ver_ventas")

    # En Ventas, el template se llama eliminar_confirm_venta.html
    return render(request, "ventas/eliminar_confirm_venta.html", {"venta": venta})