# ventas/forms.py
"""
Formularios de Ventas (ModelForms y FormSet).

Propósito:
    Exponer formularios para la creación/edición de ventas y sus líneas,
    con validaciones ligeras y widgets mínimos para buena UX.

Responsabilidades:
    - VentaForm: cabecera de la venta (cliente, fecha, descuentos, impuesto).
    - VentaProductoForm: línea de detalle (producto, cantidad, precio_unitario).
    - VentaProductoFormSet: formset inline para N líneas por venta.

Diseño/Notas:
    - Validaciones defensivas: normalizar a 0.00 cuando llega None/"".
    - La lógica de totales/impuestos vive en services (fuente de verdad).
    - El widget de fecha usa <input type="date"> para compatibilidad.
"""
from decimal import Decimal
from django import forms
from django.forms import inlineformset_factory
from .models import Venta, VentaProducto


# ─────────────────────────────────────────────────────────────────────────────
# FORM: Venta (cabecera)
# ─────────────────────────────────────────────────────────────────────────────
class VentaForm(forms.ModelForm):
    """
    Formulario de cabecera para `Venta`.

    Campos expuestos:
        - cliente, fecha, descuento_total, impuesto (importe).
          * Ojo: el porcentaje de UI se persiste en `impuesto_porcentaje` desde la vista.
                Aquí solo se captura el importe si el flujo lo requiere.

    Validación:
        - `clean_descuento_total`: normaliza None/"" → Decimal("0.00").
        - `clean_impuesto`: normaliza None/"" → Decimal("0.00").

    Notas:
        - La fecha usa <input type="date"> para UX estándar.
        - No se calculan totales aquí; lo hace services.
    """
    class Meta:
        model = Venta
        # SOLO los campos que el usuario rellena
        fields = ["cliente", "fecha", "descuento_total", "impuesto"]
        widgets = {"fecha": forms.DateInput(attrs={"type": "date"}),}

    def clean_descuento_total(self):
        v = self.cleaned_data.get("descuento_total")
        return v or Decimal("0.00")

    def clean_impuesto(self):
        v = self.cleaned_data.get("impuesto")
        return v or Decimal("0.00")
    

# ─────────────────────────────────────────────────────────────────────────────
# FORM: VentaProducto (línea)
# ─────────────────────────────────────────────────────────────────────────────
class VentaProductoForm(forms.ModelForm):
    """
    Formulario de línea para `VentaProducto`.

    Campos:
        - producto, cantidad, precio_unitario.

    Notas:
        - Las validaciones de dominio fuertes (≥0, >0) viven en el modelo.
        - Si necesitas mensajes más explícitos por campo, puedes añadir clean_* aquí.
    """
    class Meta:
        model = VentaProducto
        fields = ["producto", "cantidad", "precio_unitario"]

# ─────────────────────────────────────────────────────────────────────────────
# FORMSET: líneas de venta
# ─────────────────────────────────────────────────────────────────────────────
VentaProductoFormSet = inlineformset_factory(
    parent_model=Venta,
    model=VentaProducto,
    form=VentaProductoForm,
    extra=1, # Siempre ofrece al menos una fila en blanco
    can_delete=True, # Permite marcar/borra filas
    validate_min=True,  # pon True y min_num=1 si quieres exigir al menos 1 línea
    min_num=1,  # Al menos 1 línea por venta
)