# compras/views.py
# compras/views.py
"""
Vistas de la app 'compras'.

Flujos cubiertos:
- Crear/Editar Compra (cabecera + líneas via formset)
- Ver detalle solo-lectura (reutiliza plantilla de edición)
- Listar compras con filtros y paginación
- Eliminar compra con confirmación

Notas de diseño:
- Transacciones atómicas en operaciones críticas para mantener consistencia entre cabecera y líneas.
- La lógica de negocio pesada (stock, totales) vive en `services`.
- La validación de datos de entrada vive en `forms`/`formsets`; aquí solo orquestamos.

Dependencias:
- forms: CompraForm, CompraProductoFormSet
- models: Compra
- services: aplicar_stock_despues_de_crear_compra, reconciliar_stock_tras_editar_compra, calcular_y_guardar_totales_compra
- inventario.models.Proveedor: opciones/filtros en listado
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

from django.db.models import ProtectedError
from django.db import IntegrityError

from decimal import Decimal
# ─────────────────────────────────────────────────────────────────────────────
# CREAR
# ─────────────────────────────────────────────────────────────────────────────
@login_required
@transaction.atomic
def crear_compra(request):
    """
    Crea una compra con sus líneas, en una única transacción.
    """
    FORMS_PREFIX = "lineas"

    if request.method == "POST":
        data = request.POST.copy()
        if data.get("descuento_total") in (None, ""):
            data["descuento_total"] = "0"

        form = CompraForm(data)
        if form.is_valid():
            compra = form.save(commit=False)
            compra.usuario_id = request.user.pk
            compra.save()

            formset = CompraProductoFormSet(data, instance=compra, prefix=FORMS_PREFIX)
            if formset.is_valid():
                formset.save()

                # 1) Ajuste de stock por cada línea recién creada
                services.aplicar_stock_despues_de_crear_compra(compra)

                # 2) Ajuste de precio de referencia y stock_minimo (solo si está en 0)
                for linea in compra.lineas.all():  # related_name="lineas" en CompraProducto
                    p = linea.producto
                    # precio_unitario según tu POST: lineas-*-precio_unitario
                    precio_linea = getattr(linea, "precio_unitario", None)

                    fields_to_update = []

                    # 2.1) Actualiza precio_compra de Producto si ese campo existe
                    if hasattr(p, "precio_compra") and precio_linea is not None:
                        p.precio_compra = precio_linea
                        fields_to_update.append("precio_compra")

                    # 2.2) Si stock_minimo está vacío o 0, fijarlo al 90% de la primera cantidad
                    try:
                        sm_actual = getattr(p, "stock_minimo", 0) or 0
                    except Exception:
                        sm_actual = 0

                    if sm_actual in (None, 0):
                        try:
                            nuevo_sm = max(0, int(linea.cantidad * 0.90))
                        except Exception:
                            nuevo_sm = 0
                        # Solo agregamos si realmente hay campo
                        if hasattr(p, "stock_minimo"):
                            p.stock_minimo = nuevo_sm
                            fields_to_update.append("stock_minimo")

                    if fields_to_update:
                        # Evitar duplicados en la lista
                        p.save(update_fields=list(dict.fromkeys(fields_to_update)))

                # 3) Convertir impuesto_total (%) a tasa y recalcular totales
                raw = form.cleaned_data.get("impuesto_total")
                tasa = None
                try:
                    val = Decimal(str(raw))
                    if val <= 100:
                        tasa = (val / Decimal("100"))
                except Exception:
                    tasa = None

                services.calcular_y_guardar_totales_compra(compra, tasa_impuesto_pct=tasa)

                messages.success(request, "Compra creada correctamente.")
                return redirect("compras:detalle", pk=compra.pk)
            else:
                # Si el formset falló, limpia la cabecera creada para no dejarla colgada
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
    """
    Edita cabecera y líneas de una compra existente, reconciliando el stock.

    Flujo:
        1) Snapshot previo de líneas: {pk_linea: (producto_id, cantidad)}.
        2) POST:
            - Normaliza descuento_total.
            - Valida y guarda cabecera + formset.
            - Reconciliación de stock (sumas/restas según cambios).
            - Convierte % de impuesto a tasa y recalcula totales.
            - Mensaje de éxito y redirección a detalle.
        3) GET: muestra formulario con instancia.

    Render:
        templates/compras/editar_compra/editar_compra.html

    Notas:
        - Cualquier excepción en reconciliación se deja pasar (capturada y silenciada)
        para no bloquear la edición; el helper ya hace rollback si hay negativo.
    """
    compra = get_object_or_404(Compra, pk=pk)
    estado_previo_lineas = {l.pk: (l.producto_id, l.cantidad) for l in compra.lineas.all()}

    if request.method == "POST":
        data = request.POST.copy()
        if data.get("descuento_total") in (None, ""):
            data["descuento_total"] = "0"

        form = CompraForm(data, instance=compra)
        formset = CompraProductoFormSet(data, instance=compra, prefix="lineas")

        if form.is_valid() and formset.is_valid():
            form.save()        # deja impuesto_total=0.00; fecha normalizada
            formset.save()

            # Stock: reconciliar diferencias
            try:
                services.reconciliar_stock_tras_editar_compra(compra, estado_previo_lineas)
            except Exception:
                pass

            # Leer el % desde el form y convertir a tasa
            raw = form.cleaned_data.get("impuesto_total")
            tasa = None
            try:
                val = Decimal(str(raw))
                if val <= 100:
                    tasa = (val / Decimal("100"))
            except Exception:
                tasa = None

            # Recalcular y persistir totales
            services.calcular_y_guardar_totales_compra(compra, tasa_impuesto_pct=tasa)

            messages.success(request, "Compra actualizada correctamente.")
            return redirect("compras:detalle", pk=compra.pk)

        # Debug opcional
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

# ─────────────────────────────────────────────────────────────────────────────
# LISTAR / GESTIÓN
# ─────────────────────────────────────────────────────────────────────────────
def ver_compras(request):
    """
    Lista paginada de compras con filtros básicos.

    GET params:
        q:        texto libre (id icontains o proveedor.nombre icontains)
        desde:    fecha mínima (YYYY-MM-DD)
        hasta:    fecha máxima (YYYY-MM-DD)
        proveedor: id de proveedor

    Optimización:
        - select_related("proveedor") evita N+1 en la tabla.
        - Orden por fecha DESC e id DESC para estabilidad en resultados recientes.

    Render:
        templates/compras/lista_compra/lista.html

    Contexto:
        compras, pagina_actual, hay_paginacion, lista_proveedores,
        texto_busqueda, fecha_desde, fecha_hasta, proveedor_id_seleccionado
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
    Modo solo-lectura reutilizando la plantilla de edición.

    Qué hace:
        - Carga la compra (404 si no existe).
        - Construye CompraForm y formset de líneas con instance=compra.
        - Deshabilita todos los campos (form + formset).
        - Señaliza `readonly=True` para que la plantilla oculte acciones/JS de edición.

    Render:
        templates/compras/editar_compra/editar_compra.html
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

def detalle_compra(request, pk): #recibe request y la clave primario PK de la compra que quiero mostrar
    """
    Detalle de compra en solo-lectura.

    Alias semántico de `ver_compra`, conservado por compatibilidad de URLs.

    Render:
        templates/compras/editar_compra/editar_compra.html
    """
    #Busca la instancia de Compra con esa pk.
    #Si no existe, lanza 404 automáticamente (no hay que escribir try/except).
    compra = get_object_or_404(Compra, pk=pk)


    # Form de cabecera deshabilitado
    # Construye el formulario de cabecera (CompraForm) enlazado a la compra (instance=compra).
    #Ojo: como no es un POST, el form está no ligado (“unbound”) pero con valores iniciales de la instancia.
    form = CompraForm(instance=compra)
    for f in form.fields.values():
        f.disabled = True

    # Formset de líneas deshabilitado
    formset = CompraProductoFormSet(instance=compra)
    for frm in formset.forms: #Recorre todos los campos del form y los marca disabled. el navegador los muestra no editables y no se envían en un submit (importante: disabled ≠ readonly; disabled ni siquiera viaja en POST).
        for f in frm.fields.values(): #Construye el formset de líneas
            f.disabled = True #Para cada form de línea, deshabilita todos sus campos. Resultado: todas las filas quedan de solo lectura en el navegador.
    formset.can_delete = False # Apaga el flag can_delete para que, si tu template muestra un checkbox/botón de “eliminar línea”, no aparezca.

    # Bandera para ocultar botones/JS de edición en los parciales
    #Renderiza la plantilla compras/editar_compra/editar_compra.html.
    #Pasa el contexto:
    #compra: la instancia (para mostrar metadatos, ids, etc.).
    #form: el form de cabecera (ya disabled).
    #formset: las líneas (ya disabled).
    #readonly=True: bandera que tus partials pueden usar para ocultar botones de Guardar/Agregar/Quitar y no cargar JS de edición.
    #Devuelve el HttpResponse con todo eso.

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
    Elimina una compra previa confirmación.

    GET:
        - Muestra plantilla de confirmación (sin efectos).
    POST:
        - Intenta eliminar la compra.
        - Muestra mensaje de éxito o error (si hay referencias protegidas).
        - Redirige al listado.

    Render:
        templates/compras/eliminar_confirm.html
    """
    compra = get_object_or_404(Compra, pk=pk)
    if request.method == "POST":
        try:
            compra.delete()
            messages.success(request, "Compra eliminada correctamente.")
        except (ProtectedError, IntegrityError):
            messages.error(request, "No se puede eliminar: existen referencias asociadas.")
        return redirect("compras:ver_compras")  # <- lista de compras
    return render(request, "compras/eliminar_confirm.html", {"compra": compra})


# Alias opcional por compatibilidad con rutas antiguas
agregar_compra = crear_compra