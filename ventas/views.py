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
# Helpers genéricos (parseo seguro de números con coma/punto)
# ─────────────────────────────────────────────────────────────────────────────
def _safe_decimal(x, default="0"):
    try:
        return Decimal(str(x).replace(",", "."))
    except Exception:
        return Decimal(default)




# ─────────────────────────────────────────────────────────────────────────────
# Helper: detectar "modo cliente"
# Criterio: puede ver/crear ventas, pero NO tiene permisos de compras ni inventario.
# (Excluye naturalmente a superusuarios, que tienen todo permitido.)
# ─────────────────────────────────────────────────────────────────────────────
def _es_cliente(user) -> bool:
    """
    Determina si un usuario opera en “modo cliente”.

    Regla:
        - Debe poder ver y crear ventas.
        - No debe tener permisos de compras ni inventario.
        - Superusuarios/staff nunca son “cliente” aquí.

    Args:
        user (User): usuario autenticado.

    Returns:
        bool: True si es “cliente” según los permisos, False en caso contrario.
    """
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
    """
    Crea una venta con sus líneas en una única transacción.

    Flujo:
        1) Normaliza POST: `descuento_total` vacío → "0".
        2) Valida y guarda cabecera (VentaForm).
            - Si es “modo cliente”, auto-asigna cliente_id = request.user.pk.
        3) Valida/guarda detalles (VentaProductoFormSet).
        4) Persiste `impuesto_porcentaje` tal como lo escribió el usuario (23, 22, etc.).
        5) Aplica stock (si `services_ventas` está disponible).
        6) Recalcula totales con tasa (impuesto %) usando services (si disponible).
        7) Mensaje de éxito y redirect al detalle (readonly).

    Render:
        templates/ventas/agregar_venta/agregar_venta.html

    Notas:
        - Se mantiene `prefix="lineas"` para el formset.
        - Si el formset falla, se revierte la cabecera recién creada.
    """
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
    """
    Edita cabecera y líneas de una venta existente, reconciliando stock y totales.

    En GET: precargamos % en los inputs de cabecera (descuento_total e impuesto).
    En POST: guardamos y recalculamos importes en BD usando la tasa (impuesto% / 100).
    """
    venta = get_object_or_404(Venta, pk=pk)

    if _es_cliente(request.user) and getattr(venta, "cliente_id", None) != request.user.pk:
        raise PermissionDenied("No puedes editar ventas de otros usuarios.")

    estado_previo = {l.pk: (l.producto_id, l.cantidad) for l in venta.detalles.all()}

    def _safe_decimal(x, default="0"):
        try:
            return Decimal(str(x).replace(",", "."))
        except Exception:
            return Decimal(default)

    if request.method == "POST":
        data = request.POST.copy()
        if data.get("descuento_total") in (None, ""):
            data["descuento_total"] = "0"

        form = VentaForm(data, instance=venta)
        formset = VentaProductoFormSet(data, instance=venta, prefix="lineas")

        # % escritos por el usuario (0..100)
        imp_pct_ctx = _safe_decimal(data.get("impuesto"), "0")

        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()

            # Reconciliar stock
            if services_ventas:
                try:
                    services_ventas.reconciliar_stock_tras_editar_venta(venta, estado_previo)
                except Exception:
                    pass

            # Recalcular importes (impuesto € y total) en BD a partir del %
            tasa_pct = None
            try:
                if imp_pct_ctx <= 100:
                    tasa_pct = imp_pct_ctx / Decimal("100")
            except Exception:
                tasa_pct = None

            if services_ventas:
                services_ventas.calcular_y_guardar_totales_venta(venta, tasa_impuesto_pct=tasa_pct)

            # Persistir el % de impuesto para mostrarlo luego tal cual
            try:
                venta.impuesto_porcentaje = max(Decimal("0"), min(Decimal("100"), imp_pct_ctx))
                venta.save(update_fields=["impuesto_porcentaje"])
            except Exception:
                pass

            messages.success(request, "Venta editada correctamente.")
            return redirect("ventas:detalle", pk=venta.pk)

        return render(
            request,
            "ventas/editar_venta/editar_venta.html",
            {"venta": venta, "form": form, "formset": formset, "readonly": False},
        )

    # ---------- GET: precargar % en los inputs ----------
    form = VentaForm(instance=venta)
    formset = VentaProductoFormSet(instance=venta, prefix="lineas")

    imp_pct_ctx = getattr(venta, "impuesto_porcentaje", Decimal("0"))
    if (venta.subtotal or Decimal("0")) > 0:
        desc_pct_ctx = _round2((venta.descuento_total or Decimal("0")) * Decimal("100") / venta.subtotal)
    else:
        desc_pct_ctx = Decimal("0")

    # ⬅️ AQUÍ ESTÁ EL CAMBIO CLAVE
    form.initial["impuesto"] = imp_pct_ctx
    form.initial["descuento_total"] = desc_pct_ctx

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
    """
    Lista de ventas con filtros y paginación.

    Reglas de acceso:
        - “Modo cliente” solo ve sus propias ventas.

    Filtros (GET):
        q       → id icontains | cliente.username icontains
        desde   → fecha mínima (YYYY-MM-DD)
        hasta   → fecha máxima (YYYY-MM-DD)
        cliente → id de usuario (cliente)

    Render:
        templates/ventas/lista_venta/lista_venta.html

    Contexto:
        ventas, pagina_actual, hay_paginacion, lista_clientes,
        texto_busqueda, fecha_desde, fecha_hasta, cliente_id_seleccionado
    """
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
    """
    Vista de solo lectura para una venta (reutiliza plantilla de edición).

    Reglas de acceso:
        - “Modo cliente” solo puede ver sus propias ventas.

    Qué hace:
        - Deshabilita todos los campos del form y del formset.
        - Oculta controles de eliminación en el formset.
        - Calcula `ganancia` fija sobre el `subtotal` (criterio actual).
        - Expone `impuesto_porcentaje` tal como fue guardado.

    Render:
        templates/ventas/editar_venta/editar_venta.html
    """
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

    desc_pct = Decimal("0")
    if (venta.subtotal or Decimal("0")) > 0:
        desc_pct = _round2((venta.descuento_total or Decimal("0")) * Decimal("100") / venta.subtotal)

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
            "descuento_porcentaje": desc_pct,
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
    """
    Elimina una venta previa confirmación.

    Reglas de acceso:
        - “Modo cliente” solo puede eliminar sus propias ventas (si tu negocio lo permite).

    POST:
        - Intenta eliminar, muestra flash de éxito o error y redirige al listado.

    GET:
        - Renderiza plantilla de confirmación.

    Render:
        templates/ventas/eliminar_confirm_venta.html
    """
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
    """
    Redondeo financiero a 2 decimales (ROUND_HALF_UP).

    Args:
        x (Decimal): valor a redondear (permite None → 0).

    Returns:
        Decimal: valor con 2 decimales.
    """
    return (x or Decimal("0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

@transaction.atomic
def calcular_y_guardar_totales_venta(venta: Venta, tasa_impuesto_pct: Decimal | None = None) -> Venta:
    """
    Recalcula subtotal, impuesto (importe) y total de una VENTA, guardándolos en la BD.

    Reglas:
        - subtotal := SUM(cantidad * precio_unitario) (precisión intermedia 6 decimales).
        - Respeta `venta.descuento_total` (importe absoluto).
        - Si `tasa_impuesto_pct` se pasa (ej. 0.23), calcula impuesto = base * tasa, donde
        base = max(0, subtotal - descuento_total).
        - total = subtotal - descuento_total + impuesto.
        - Redondeo financiero a 2 decimales.

    Args:
        venta (Venta): instancia existente con líneas guardadas.
        tasa_impuesto_pct (Decimal | None): tasa fraccional (0.23) o None para mantener impuesto actual.

    Returns:
        Venta: instancia con campos actualizados y persistidos (subtotal, impuesto, total).
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