"""
Formularios de Inventario (ModelForms para Proveedor y Producto).

Responsabilidades:
- Exponer formularios basados en modelos para CRUD en vistas/templates.
- Incluir widgets mínimos y validaciones de integridad en `ProductoForm.clean()`.

Diseño:
- Mantener `fields="__all__"` mientras el modelo esté estable (rápida iteración).
- No tocar nombres de campos no existentes (evita KeyError en widgets/labels).
"""

from django import forms
from .models import Proveedor, Producto


# ─────────────────────────────────────────────────────────────────────────────
# FORM: ProveedorForm
# Propósito: CRUD de Proveedor sin personalizaciones extra.
# ─────────────────────────────────────────────────────────────────────────────
class ProveedorForm(forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = "__all__"


# ─────────────────────────────────────────────────────────────────────────────
# FORM: ProductoForm
# Propósito: CRUD de Producto con widgets básicos y validación defensiva.
# ─────────────────────────────────────────────────────────────────────────────
class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        # Temporalmente incluimos todo para que no falle por un campo mal referenciado.
        fields = "__all__"
        # IMPORTANTE: no pongas aquí labels/help_texts/widgets con claves inexistentes.
        widgets = {
            "nombre": forms.TextInput(attrs={"placeholder": "Ej: Papel A4 80g"}),
            "descripcion": forms.Textarea(attrs={"rows": 3, "placeholder": "Detalle opcional"}),
        }

    # Valida solo nombres que EXISTAN realmente en tu modelo:
    def clean(self):
        """
        Validación defensiva de precio y stock.

        Reglas:
        - `precio_compra` (o `precio`) no puede ser negativo.
        - `stock` (o `stock_inicial`) no puede ser negativo.

        Notas:
        - Se toleran alias históricos (`precio`, `stock_inicial`) para compatibilidad.
        - Si cambias nombres en el modelo, ajusta aquí las claves de `add_error`.
        """
        cleaned = super().clean()
        # Ajusta estos nombres a los reales de tu modelo:
        precio = cleaned.get("precio_compra") or cleaned.get("precio")
        stock  = cleaned.get("stock_inicial") or cleaned.get("stock")
        if precio is not None and precio < 0:
            self.add_error("precio_compra" if "precio_compra" in self.fields else "precio",
                        "El precio de compra no puede ser negativo.")
        if stock is not None and stock < 0:
            self.add_error("stock_inicial" if "stock_inicial" in self.fields else "stock",
                        "El stock no puede ser negativo.")
        return cleaned