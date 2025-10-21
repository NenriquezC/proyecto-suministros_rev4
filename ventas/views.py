from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, F, Sum, DecimalField, ExpressionWrapper
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied

from .forms import VentaForm, VentaProductoFormSet
from .models import Venta, VentaProducto
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import ProtectedError
from django.db import IntegrityError

try:
    from . import services as services_ventas
except Exception:
    services_ventas = None

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# Helper: detectar "modo cliente"
# Criterio: puede ver/crear ventas, pero NO tiene permisos de compras ni inventario.
# (Excluye naturalmente a superusuarios, que tienen todo permitido.)
# ─────────────────────────────────────────────────────────────────────────────
def _es_cliente(user) -> bool:
    if user.is_superuser or user.is_staff:
        return False
    return (
        user.has_perm("ventas.view_venta")
        and user.has_perm("ventas.add_venta")
        and not user.has_perm("compras.view_compra")
        and not user.has_perm("inventario.view_producto")
    )


# ─────────────────────────────────────────────────────────────────────────────
# CREAR
# ─────────────────────────────────────────────────────────────────────────────
@login_required
@permission_required("ventas.add_venta", raise_exception=True)
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

            # MODO CLIENTE: auto-asignar el cliente a quien crea la venta
            if _es_cliente(request.user):
                if hasattr(venta, "cliente_id"):
                    venta.cliente_id = request.user.pk

            venta.save()

            formset = VentaProductoFormSet(data, instance=venta, prefix=PREFIX)
            if formset.is_valid():
                formset.save()

                # 🟢 Guardar el porcentaje original que el usuario escribió (23, 22, etc.)
                try:
                    raw = (data.get("impuesto") or "").replace(",", ".")
                    venta.impuesto_porcentaje = Decimal(raw or "0")
                    venta.save(update_fields=["impuesto_porcentaje"])
                except Exception:
                    venta.impuesto_porcentaje = Decimal("0")
                    venta.save(update_fields=["impuesto_porcentaje"])

                # Aplicar cambios de stock
                if services_ventas:
                    services_ventas.aplicar_stock_despues_de_crear_venta(venta)

                # Calcular totales en base al porcentaje (para guardar el importe correcto)
                if services_ventas:
                    try:
                        raw = (data.get("impuesto") or "").replace(",", ".")
                        tasa_pct = Decimal(raw or "0") / Decimal("100")
                        services_ventas.calcular_y_guardar_totales_venta(
                            venta, tasa_impuesto_pct=tasa_pct
                        )
                    except Exception:
                        pass

                messages.success(request, "Venta creada exitosamente.")
                return redirect("ventas:detalle", pk=venta.pk)
            else:
                # Si el formset falla, revertimos la cabecera creada
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
@permission_required("ventas.change_venta", raise_exception=True)
@transaction.atomic
def editar_venta(request, pk):
    venta = get_object_or_404(Venta, pk=pk)

    # MODO CLIENTE: sólo puede editar sus propias ventas
    if _es_cliente(request.user) and getattr(venta, "cliente_id", None) != request.user.pk:
        raise PermissionDenied("No puedes editar ventas de otros usuarios.")

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
                # Recalcular totales con tasa si viene en el form
                try:
                    raw = (data.get("impuesto") or "").replace(",", ".")
                    tasa_pct = Decimal(raw or "0") / Decimal("100")
                    services_ventas.calcular_y_guardar_totales_venta(venta, tasa_impuesto_pct=tasa_pct)
                except Exception:
                    pass

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
@permission_required("ventas.view_venta", raise_exception=True)
def ver_ventas(request):
    ventas_qs = Venta.objects.select_related("cliente").order_by("-fecha", "-id")

    # MODO CLIENTE: sólo ve sus ventas
    if _es_cliente(request.user):
        ventas_qs = ventas_qs.filter(cliente_id=request.user.pk)

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
@permission_required("ventas.view_venta", raise_exception=True)
def ver_venta(request, pk):
    venta = get_object_or_404(Venta.objects.select_related("cliente"), pk=pk)

    # MODO CLIENTE: sólo puede ver sus propias ventas
    if _es_cliente(request.user) and getattr(venta, "cliente_id", None) != request.user.pk:
        raise PermissionDenied("No puedes ver ventas de otros usuarios.")

    form = VentaForm(instance=venta)
    for f in form.fields.values():
        f.disabled = True

    formset = VentaProductoFormSet(instance=venta)
    for frm in formset.forms:
        for f in frm.fields.values():
            f.disabled = True
    formset.can_delete = False

    # 🔹 Aseguramos que el valor esté disponible
    impuesto_porcentaje = getattr(venta, "impuesto_porcentaje", Decimal("0"))

    # 🔹 Ganancia (fija) calculada sobre el SUBTOTAL (mismo criterio que en "agregar")
    ganancia_pct_fija = Decimal("50")  # ← mismo valor que el input ganancia_pct del formulario de agregar
    ganancia = _round2((venta.subtotal or Decimal("0")) * ganancia_pct_fija / Decimal("100"))

    return render(
        request,
        "ventas/editar_venta/editar_venta.html",
        {
            "form": form,
            "formset": formset,
            "venta": venta,
            "readonly": True,
            "impuesto_porcentaje": impuesto_porcentaje,  # 🔹 se envía directo al template
            "ganancia": ganancia,
        },
    )

detalle = ver_venta  # alias


# ─────────────────────────────────────────────────────────────────────────────
# ELIMINAR
# ─────────────────────────────────────────────────────────────────────────────
@login_required
@permission_required("ventas.delete_venta", raise_exception=True)
@transaction.atomic
def eliminar_venta(request, pk):
    venta = get_object_or_404(Venta, pk=pk)

    # MODO CLIENTE: sólo puede eliminar sus propias ventas (si tu negocio lo permite)
    if _es_cliente(request.user) and getattr(venta, "cliente_id", None) != request.user.pk:
        raise PermissionDenied("No puedes eliminar ventas de otros usuarios.")

    if request.method == "POST":
        try:
            venta.delete()
            messages.success(request, "Venta eliminada correctamente.")
        except (ProtectedError, IntegrityError):
            messages.error(request, "No se puede eliminar: la venta está referenciada por otros registros.")
        return redirect("ventas:ver_ventas")

    # confirma en esta plantilla
    return render(request, "ventas/eliminar_confirm_venta.html", {"venta": venta})


# ─────────────────────────────────────────────────────────────────────────────
# Utilidades de totales
# ─────────────────────────────────────────────────────────────────────────────
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

    venta.subtotal = _round2(subtotal_calc)

    if tasa_impuesto_pct is not None:
        base = max(Decimal("0"), venta.subtotal - (venta.descuento_total or Decimal("0")))
        venta.impuesto = _round2(base * Decimal(str(tasa_impuesto_pct)))

    venta.total = _round2(venta.subtotal - (venta.descuento_total or Decimal("0")) + (venta.impuesto or Decimal("0")))
    venta.save(update_fields=["subtotal", "impuesto", "total"])
    return venta