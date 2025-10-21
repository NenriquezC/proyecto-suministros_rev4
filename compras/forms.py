# compras/forms.py
"""
Formularios de la app 'compras'.

Responsabilidades:
- CompraForm: formulario de cabecera (proveedor, fecha, descuentos, impuestos).
- CompraProductoForm: formulario de línea (producto, cantidad, precio_unitario).
- CompraProductoFormSet: formset inline para gestionar N líneas por compra.

Diseño:
- Validaciones ligeras y explícitas en el form (p. ej., no negatividad por campo).
- Lógica de negocio pesada (cálculo de totales/stock) vive en services/modelos.
- Widgets acordes a la UI (datetime-local) y mensajes de error personalizables.
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

    - Campo 'fecha' se maneja como <input type="date">.
    - Campo 'impuesto_total' en la UI se usa como PORCENTAJE (ej. 23),
      pero NO se guarda directamente; el monto final lo calcula services.
    - En edición, se muestra el PORCENTAJE calculado desde los importes guardados.
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
        - Convierte date -> datetime 00:00 con tz.
        - **No** guarda el valor ingresado en 'impuesto_total' (porcentaje);
        lo pone a 0.00 porque el cálculo real lo hará 'services'.
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

    Validaciones:
        - cantidad > 0
        - precio_unitario ≥ 0

    Mensajes de error personalizados para mejorar feedback en UI.
    """
    class Meta:
        model = CompraProducto
        fields = ['producto', 'cantidad', 'precio_unitario']

    # Validaciones por campo (claras y suficientes)
    def clean_cantidad(self):
        """
        cantidad debe ser > 0 (refuerza el validator del modelo con mensaje claro).
        """
        cantidad = self.cleaned_data.get('cantidad')
        if cantidad is None or cantidad <= 0:
            raise forms.ValidationError('La cantidad debe ser mayor que 0.')
        return cantidad

    def clean_precio_unitario(self):
        """
        precio_unitario debe ser ≥ 0 (refuerza el validator del modelo con mensaje claro).
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