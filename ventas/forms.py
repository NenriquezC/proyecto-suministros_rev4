# ventas/forms.py
# ventas/forms.py
from decimal import Decimal
from django import forms
from django.forms import inlineformset_factory
from .models import Venta, VentaProducto
class VentaForm(forms.ModelForm):
    class Meta:
        model = Venta
        # SOLO los campos que el usuario rellena
        fields = ["cliente", "fecha", "descuento_total", "impuesto"]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}),
        }

    def clean_descuento_total(self):
        v = self.cleaned_data.get("descuento_total")
        return v or Decimal("0.00")

    def clean_impuesto(self):
        v = self.cleaned_data.get("impuesto")
        return v or Decimal("0.00")

class VentaProductoForm(forms.ModelForm):
    class Meta:
        model = VentaProducto
        fields = ["producto", "cantidad", "precio_unitario", "descuento"]

# *** ESTO ES LO CLAVE ***
VentaProductoFormSet = inlineformset_factory(
    parent_model=Venta,
    model=VentaProducto,
    form=VentaProductoForm,
    extra=1,
    can_delete=True,
    validate_min=False,  # pon True y min_num=1 si quieres exigir al menos 1 línea
    min_num=0,
)