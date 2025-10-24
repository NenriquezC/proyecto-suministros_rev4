# compras/forms.py
"""
Formularios de la app 'compras'.

Propósito:
    Definir los formularios y formsets necesarios para crear/editar una Compra y
    sus líneas (CompraProducto), manteniendo las validaciones de UI y delegando
    la lógica de negocio pesada (cálculos/stock) a models/services.

Responsabilidades:
    - CompraForm: cabecera de la compra (proveedor, fecha, descuentos, impuesto % en UI).
    - CompraProductoForm: línea de detalle (producto, cantidad, precio_unitario).
    - CompraProductoFormSet: conjunto inline para N líneas asociado a una Compra.

Dependencias/Assume:
    - Los modelos Compra y CompraProducto están definidos y con validadores básicos.
    - El cálculo de totales/impuestos/stock se realizará en services/models (no aquí).
    - La UI espera que `impuesto_total` se interprete como PORCENTAJE al editar/crear.

Diseño/UX:
    - Widgets acordes (fecha con <input type="date">).
    - Errores de validación con mensajes claros y orientados a la acción.
    - Se muestra el impuesto como % para edición (derivado de montos guardados).

Notas:
    - Este módulo no persiste el valor de impuesto como dinero en save(); lo fija a 0
    porque el cálculo real se hace aguas abajo (services). Así se evita doble cómputo.
    - Se preserva el comportamiento existente. Solo se agregan docstrings y comentarios.
"""
from decimal import Decimal, ROUND_HALF_UP
from decimal import Decimal
from django import forms
from django.forms import inlineformset_factory
from .models import Compra, CompraProducto
from django.utils import timezone
from datetime import datetime, time

# ─────────────────────────────────────────────────────────────────────────────
# Formulario de cabecera
# ─────────────────────────────────────────────────────────────────────────────
class CompraForm(forms.ModelForm):
    """
    Form de cabecera para 'Compra'.

    Qué hace:
        - Provee campos de cabecera: proveedor, fecha (date), descuento %, descuento €,
        e "impuesto_total" entendido como PORCENTAJE en la UI.
        - En edición (no bound), precarga:
            * fecha = instance.fecha.date()
            * impuesto_total (%) derivado de los montos guardados (imp/(subtotal-descuento)*100)

    Por qué así:
        - La fecha se trata como `date` para UX más limpia y luego se convierte a
        datetime aware (00:00) en save(), respetando la TZ del proyecto.
        - El impuesto como % en UI evita confusión al editar (los montos reales
            os recalcula la capa de negocio).

    Notas:
        - No persiste el valor de 'impuesto_total' (porcentaje) como dinero al guardar:
        se fija a Decimal('0.00') intencionalmente (services hará el cálculo real).
    """

    fecha = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        input_formats=['%Y-%m-%d'],
        required=True,
        label='Fecha'
    )

    class Meta:
        model = Compra
        fields = ['proveedor', 'fecha', 'descuento_porcentaje', 'descuento_total', 'impuesto_total']
        # Nota: 'impuesto_total' se usa como % en la UI.

    def __init__(self, *args, **kwargs):
        """
        Inicializa el form.

        Comportamiento:
            - Si el form NO está "bound" (GET / edición), precarga la fecha con instance.fecha.date().
            - Si existe instance con montos, computa un porcentaje de impuesto visual (2 decimales)
            a partir de subtotal, descuento_total e impuesto_total almacenados.

        No cambia estado persistente; solo prepara valores iniciales para la UI.
        """
        super().__init__(*args, **kwargs)

        # En EDITAR (no bound): precargar fecha y porcentaje de impuesto
        if not self.is_bound:
            inst = getattr(self, "instance", None)
            if inst and getattr(inst, "fecha", None):
                try:
                    self.initial["fecha"] = inst.fecha.date()
                except Exception:
                    pass

            # Mostrar porcentaje de impuesto (no el dinero) si hay datos
            if inst and inst.pk:
                try:
                    subtotal = Decimal(inst.subtotal or 0)
                    desc = Decimal(inst.descuento_total or 0)
                    base = subtotal - desc
                    imp = Decimal(inst.impuesto_total or 0)
                    if base > 0:
                        pct = (imp / base) * Decimal('100')
                        # Redondeo visual a 2 decimales
                        pct = pct.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                        self.initial["impuesto_total"] = pct
                except Exception:
                    pass

        # Opcional UX: aclarar que es porcentaje
        self.fields["impuesto_total"].label = "Impuesto total (%)"

    def save(self, commit=True):
        """
        Guarda la instancia sin romper la responsabilidad de cálculo en services.

        Flujo:
            1) Convierte la 'fecha' (date) a datetime aware 00:00 en TZ actual.
            2) Fuerza `impuesto_total = Decimal('0.00')` porque el monto real lo calculará services.
            3) Persiste si commit=True y ejecuta save_m2m().

        Returns:
            Compra: instancia persistida (o sin persistir si commit=False).
        """
        instance = super().save(commit=False)

        # Fecha → datetime aware
        d = self.cleaned_data.get("fecha")
        if d:
            dt = datetime.combine(d, time(0, 0))
            instance.fecha = timezone.make_aware(dt, timezone.get_current_timezone())

        # No persistir el porcentaje como dinero:
        instance.impuesto_total = Decimal('0.00')

        if commit:
            instance.save()
            self.save_m2m()
        return instance

    def clean(self):
        data = super().clean()
        # No negativos
        for f in ('descuento_porcentaje', 'descuento_total', 'impuesto_total'):
            v = data.get(f)
            if v is not None and v < 0:
                self.add_error(f, 'No puede ser negativo.')
        return data
# ─────────────────────────────────────────────────────────────────────────────
# Formulario de línea (detalle)
# ─────────────────────────────────────────────────────────────────────────────
class CompraProductoForm(forms.ModelForm):
    """
    Form de línea para 'CompraProducto'.

    Qué valida:
        - cantidad > 0
        - precio_unitario ≥ 0

    Por qué así:
        - Reforzamos con mensajes claros lo que ya suelen cubrir validadores del modelo,
        dando feedback inmediato en la interfaz.
    """
    class Meta:
        model = CompraProducto
        fields = ['producto', 'cantidad', 'precio_unitario']

    # Validaciones por campo (claras y suficientes)
    def clean_cantidad(self):
        """
        Valida que 'cantidad' sea > 0.

        Returns:
            Decimal|int: cantidad válida (> 0).

        Raises:
            forms.ValidationError: si cantidad es None o <= 0.
        """
        cantidad = self.cleaned_data.get('cantidad')
        if cantidad is None or cantidad <= 0:
            raise forms.ValidationError('La cantidad debe ser mayor que 0.')
        return cantidad

    def clean_precio_unitario(self):
        """
        Valida que 'precio_unitario' sea ≥ 0.

        Returns:
            Decimal: precio_unitario válido (≥ 0).

        Raises:
            forms.ValidationError: si es None o negativo.
        """
        pu = self.cleaned_data.get('precio_unitario')
        if pu is None or pu < Decimal('0'):
            raise forms.ValidationError('El precio unitario no puede ser negativo.')
        return pu

# ─────────────────────────────────────────────────────────────────────────────
# Formset inline (líneas de compra)
# ─────────────────────────────────────────────────────────────────────────────
CompraProductoFormSet = inlineformset_factory(
    parent_model=Compra,
    model=CompraProducto,
    form=CompraProductoForm,
    fields=['producto', 'cantidad', 'precio_unitario'],   # sin 'descuento' (por decisión de UI/negocio)
    extra=1,  # Mínimo 1 fila “en blanco” para añadir
    can_delete=True,  # Permite marcar DELETE (modo “suave” en tu JS)
    validate_min=True, # Enforce min_num a nivel de validación
    min_num=1  # Al menos 1 línea por compra
)