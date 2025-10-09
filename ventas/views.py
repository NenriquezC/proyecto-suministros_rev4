# ventas/views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.db.models import F, Sum, DecimalField, ExpressionWrapper
from .forms import VentaForm, VentaProductoFormSet
from .models import Venta, VentaProducto

from decimal import ROUND_HALF_UP, Decimal

try:
    from . import services as services_ventas
except Exception:
    services_ventas = None

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# CREAR
# ─────────────────────────────────────────────────────────────────────────────
@login_required
@transaction.atomic
def crear_venta(request):
    PREFIX = "lineas"

    if request.method == "POST":
        data = request.POST.copy()
        if data.get("descuento_total") in (None, ""):
            data["descuento_total"] = "0"

        form = VentaForm(data)
        if form.is_valid():
            venta = form.save(commit=False)
            # venta.usuario_id = request.user.pk  # si corresponde
            venta.save()

            formset = VentaProductoFormSet(data, instance=venta, prefix=PREFIX)
            if formset.is_valid():
                formset.save()

                # ⬇️⬇️⬇️ ESTA LÍNEA ES LA CLAVE ⬇️⬇️⬇️
                if services_ventas:
                    services_ventas.aplicar_stock_despues_de_crear_venta(venta)
                # ⬆️⬆️⬆️ --------------------------- ⬆️⬆️⬆️



                # ───── AQUI: calcular tasa e invocar servicio con tasa ─────
                if services_ventas:
                    try:
                        raw = (data.get("impuesto") or "").replace(",", ".")  # "23" → "23" / "23,5" → "23.5"
                        tasa_pct = Decimal(raw or "0") / Decimal("100")       # 23 → 0.23
                        services_ventas.calcular_y_guardar_totales_venta(venta, tasa_impuesto_pct=tasa_pct)
                    except Exception:
                        pass
                # ──────────────────────────────────────────────────────────

                messages.success(request, "Venta creada exitosamente.")
                return redirect("ventas:detalle", pk=venta.pk)
            else:
                venta.delete()
        else:
            formset = VentaProductoFormSet(data, instance=Venta(), prefix=PREFIX)
    else:
        form = VentaForm()
        formset = VentaProductoFormSet(instance=Venta(), prefix=PREFIX)

    return render(
        request,
        "ventas/agregar_venta/agregar_venta.html",
        {"form": form, "formset": formset},
    )

agregar_venta = crear_venta  # alias


# ─────────────────────────────────────────────────────────────────────────────
# EDITAR
# ─────────────────────────────────────────────────────────────────────────────
@login_required
@transaction.atomic
def editar_venta(request, pk):
    venta = get_object_or_404(Venta, pk=pk)
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

            if services_ventas:
                try:
                    services_ventas.reconciliar_stock_tras_editar_venta(venta, estado_previo)
                except Exception:
                    pass
                # ───── AQUI: calcular tasa e invocar servicio con tasa ─────
                try:
                    raw = (data.get("impuesto") or "").replace(",", ".")
                    tasa_pct = Decimal(raw or "0") / Decimal("100")
                    services_ventas.calcular_y_guardar_totales_venta(venta, tasa_impuesto_pct=tasa_pct)
                except Exception:
                    pass
                # ──────────────────────────────────────────────────────────

            messages.success(request, "Venta editada correctamente.")
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
    ventas_qs = Venta.objects.select_related("cliente").order_by("-fecha", "-id")

    q = request.GET.get("q", "").strip()
    desde = request.GET.get("desde")
    hasta = request.GET.get("hasta")
    cliente_id = request.GET.get("cliente")

    if q:
        ventas_qs = ventas_qs.filter(Q(id__icontains=q) | Q(cliente__username__icontains=q))
    if desde:
        ventas_qs = ventas_qs.filter(fecha__gte=desde)
    if hasta:
        ventas_qs = ventas_qs.filter(fecha__lte=hasta)
    if cliente_id:
        ventas_qs = ventas_qs.filter(cliente_id=cliente_id)

    paginator = Paginator(ventas_qs, 20)
    page = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "ventas/lista_venta/lista_venta.html",
        {
            "ventas": page.object_list,
            "pagina_actual": page,
            "hay_paginacion": page.has_other_pages(),
            "lista_clientes": User.objects.all().order_by("username"),
            "texto_busqueda": q,
            "fecha_desde": desde,
            "fecha_hasta": hasta,
            "cliente_id_seleccionado": cliente_id,
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# VER (SOLO LECTURA)
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

    return render(
        request,
        "ventas/editar_venta/editar_venta.html",
        {"form": form, "formset": formset, "venta": venta, "readonly": True},
    )


detalle = ver_venta  # alias


# ─────────────────────────────────────────────────────────────────────────────
# ELIMINAR
# ─────────────────────────────────────────────────────────────────────────────
@login_required
@transaction.atomic
def eliminar_venta(request, pk):

    venta = get_object_or_404(Venta, pk=pk)
    if request.method == "POST":
        venta.delete()
        messages.success(request, "Venta eliminada.")
        return redirect("ventas:ver_ventas")
    return render(request, "ventas/eliminar_confirm_venta.html", {"venta": venta})





def _round2(x: Decimal) -> Decimal:
    return (x or Decimal("0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

@transaction.atomic
def calcular_y_guardar_totales_venta(venta: Venta, tasa_impuesto_pct: Decimal | None = None) -> Venta:
    """
    Recalcula subtotal, impuesto (importe) y total de una VENTA, guardándolos en la BD.
    - Suma en BD: SUM(cantidad * precio_unitario)
    - Respeta venta.descuento_total (importe absoluto)
    - Si se pasa `tasa_impuesto_pct` (ej. 0.23), recalcula `venta.impuesto` como base * tasa
    - total = subtotal - descuento_total + impuesto
    """
    total_linea = ExpressionWrapper(
        F("cantidad") * F("precio_unitario"),
        output_field=DecimalField(max_digits=16, decimal_places=6),
    )
    agg = VentaProducto.objects.filter(venta=venta).aggregate(subtotal=Sum(total_linea))
    subtotal_calc = agg["subtotal"] or Decimal("0")

    # Subtotal (guardado)
    venta.subtotal = _round2(subtotal_calc)

    # Impuesto (importe)
    if tasa_impuesto_pct is not None:
        base = max(Decimal("0"), venta.subtotal - (venta.descuento_total or Decimal("0")))
        venta.impuesto = _round2(base * Decimal(str(tasa_impuesto_pct)))

    # Total
    venta.total = _round2(venta.subtotal - (venta.descuento_total or Decimal("0")) + (venta.impuesto or Decimal("0")))

    venta.save(update_fields=["subtotal", "impuesto", "total"])
    return venta