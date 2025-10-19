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
    """

    # ✅ Forzamos solo FECHA en el form
    fecha = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        input_formats=['%Y-%m-%d'],
        required=True,
        label='Fecha'
    )

    class Meta:
        model = Compra
        fields = ['proveedor', 'fecha', 'descuento_porcentaje', 'descuento_total', 'impuesto_total']
        # (Opcional) puedes omitir widgets aquí; ya definimos el de 'fecha' arriba.

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ✅ En EDITAR, precarga el input <type="date"> con la fecha guardada
        if not self.is_bound:
            inst = getattr(self, "instance", None)
            if inst and getattr(inst, "fecha", None):
                try:
                    self.initial["fecha"] = inst.fecha.date()
                except Exception:
                    pass

    def save(self, commit=True):
        """
        Convierte date -> datetime 00:00 (tz local) para el DateTimeField del modelo.
        """
        instance = super().save(commit=False)
        d = self.cleaned_data.get("fecha")
        if d:
            dt = datetime.combine(d, time(0, 0))
            instance.fecha = timezone.make_aware(dt, timezone.get_current_timezone())
        if commit:
            instance.save()
            self.save_m2m()
        return instance



    def clean(self):
        """
        Validación a nivel formulario (cruzada opcional y reglas genéricas).

        Reglas actuales:
            - No negatividad en campos numéricos de entrada.
        Notas:
            - 'descuento_porcentaje' también está acotado por el modelo (0..100);
            este chequeo mantiene feedback inmediato a nivel de form.
            - Si centralizas min_value en el modelo (validators), puedes limitarte
            a delegar y solo personalizar mensajes vía Meta.error_messages.
        """
        data = super().clean()
        # Reglas generales: nada negativo
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