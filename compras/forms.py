# compras/forms.py
"""
Formularios de 'compras'.

Incluye:
- CompraForm: cabecera de la compra (proveedor/fecha/descuentos/impuestos).
- CompraProductoForm: líneas (producto/cantidad/precio_unitario).
- CompraProductoFormSet: formset inline para gestionar N líneas por compra.

Criterios:
- Validaciones simples y explícitas (>=0, >0 donde corresponda).
- Widgets acordes (datetime-local para compatibilidad con navegadores).
- Sin lógica de negocio/persistencia: eso vive en services o modelos.
"""
from decimal import Decimal
from django import forms
from django.forms import inlineformset_factory
from .models import Compra, CompraProducto

# -------------------------
# FORMULARIO CABECERA
# -------------------------
class CompraForm(forms.ModelForm):
    """
    Form de cabecera para 'Compra'.

    Expone únicamente campos de UI acordados y aplica validaciones
    genéricas de no-negatividad a descuentos/impuestos.

    NOTA: El cálculo real de totales debe residir en services/modelo; aquí
    solo se valida entrada del usuario.
    """
    class Meta:
        model = Compra
        # Solo los campos acordados en cabecera
        fields = ['proveedor', 'fecha', 'descuento_porcentaje', 'descuento_total', 'impuesto_total']
        #codigo para personalizar el error al no llenar los campos--------------------------------
        error_messages = {
            "proveedor": {
                "required": "*"
            },
            "fecha": {
                "required": "*"
            },
            "descuento_porcentaje": {
                "required": "Escribe el % de descuento (0 si no aplica)."
            },
        }
        #-------------------------------------------------------------------------------------------
        widgets = {'fecha': forms.DateTimeInput(attrs={'type': 'datetime-local'})}

    def clean(self):
        """
        Validación a nivel de formulario:
        - Reglas genéricas de no-negatividad en descuentos/impuestos.
        - (Opcional) Cohesión: si % > 0 y total descuento manual > 0, avisar conflicto.
        """
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
    """
    Form de línea para 'CompraProducto'.

    Valida entradas mínimas:
    - cantidad > 0
    - precio_unitario >= 0
    """
    class Meta:
        model = CompraProducto
        fields = ['producto', 'cantidad', 'precio_unitario']

    # Validaciones por campo (claras y suficientes)
    def clean_cantidad(self):
        """
        cantidad debe ser > 0.
        """
        cantidad = self.cleaned_data.get('cantidad')
        if cantidad is None or cantidad <= 0:
            raise forms.ValidationError('La cantidad debe ser mayor que 0.')
        return cantidad

    def clean_precio_unitario(self):
        """
        precio_unitario debe ser >= 0.
        """
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
    fields=['producto', 'cantidad', 'precio_unitario'],   # sin 'descuento' (por decisión de UI/negocio)
    extra=1,  # Mínimo 1 fila “en blanco” para añadir
    can_delete=True,  # Permite marcar DELETE (modo “suave” en tu JS)
    validate_min=True, # Enforce min_num a nivel de validación
    min_num=1  # Al menos 1 línea por compra
)