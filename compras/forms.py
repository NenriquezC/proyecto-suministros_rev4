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

# ─────────────────────────────────────────────────────────────────────────────
# Formulario de cabecera
# ─────────────────────────────────────────────────────────────────────────────
class CompraForm(forms.ModelForm):
    """
    Form de cabecera para 'Compra'.

    Expone los campos visibles en UI y aplica validaciones mínimas de entrada.
    Notas:
        - El cálculo de subtotal/impuestos/total NO se hace aquí (ver services).
        - Si quieres permitir que 'descuento_total' quede vacío y se trate como 0,
        es mejor marcarlo como no requerido en el form en lugar de normalizar en la vista.
    """

    class Meta:
        model = Compra
        # Solo los campos acordados en cabecera
        fields = ['proveedor', 'fecha', 'descuento_porcentaje', 'descuento_total', 'impuesto_total']
        #codigo para personalizar el error al no llenar los campos--------------------------------
        """error_messages = {
            "proveedor": {
                "required": "Campo obligatorio"
            },
            "fecha": {
                "required": "Campo obligatorio"
            },
            "descuento_porcentaje": {
                "required": "Escribe el % de descuento (0 si no aplica)."
            },
        }"""
        #-------------------------------------------------------------------------------------------
        widgets = {'fecha': forms.DateTimeInput(attrs={'type': 'datetime-local'})}

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