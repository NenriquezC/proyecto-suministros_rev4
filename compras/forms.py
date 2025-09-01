# compras/forms.py
from decimal import Decimal
from django import forms
from django.forms import inlineformset_factory
from .models import Compra, CompraProducto

# -------------------------
# FORMULARIO CABECERA
# -------------------------
class CompraForm(forms.ModelForm):
    class Meta:
        model = Compra
        # Solo los campos acordados en cabecera
        fields = ['proveedor', 'fecha', 'descuento_porcentaje', 'descuento_total', 'impuesto_total']
        widgets = {'fecha': forms.DateTimeInput(attrs={'type': 'datetime-local'})}

    def clean(self):
        data = super().clean()
        # Reglas generales: nada negativo
        for f in ('descuento_porcentaje', 'descuento_total', 'impuesto_total'):
            v = data.get(f)
            if v is not None and v < 0:
                self.add_error(f, 'No puede ser negativo.')
        return data

# -------------------------
# FORMULARIO DETALLE (LÍNEAS)
# -------------------------
class CompraProductoForm(forms.ModelForm):
    class Meta:
        model = CompraProducto
        fields = ['producto', 'cantidad', 'precio_unitario']

    # Validaciones por campo (claras y suficientes)
    def clean_cantidad(self):
        cantidad = self.cleaned_data.get('cantidad')
        if cantidad is None or cantidad <= 0:
            raise forms.ValidationError('La cantidad debe ser mayor que 0.')
        return cantidad

    def clean_precio_unitario(self):
        pu = self.cleaned_data.get('precio_unitario')
        if pu is None or pu < Decimal('0'):
            raise forms.ValidationError('El precio unitario no puede ser negativo.')
        return pu

# -------------------------
# FORMSET INLINE
# -------------------------
CompraProductoFormSet = inlineformset_factory(
    parent_model=Compra,
    model=CompraProducto,
    form=CompraProductoForm,
    fields=['producto', 'cantidad', 'precio_unitario'],  # sin 'descuento'
    extra=1,
    can_delete=True,
    validate_min=True,
    min_num=1
)