"""
Formularios de Inventario (ModelForms para Proveedor y Producto).

Propósito:
    Exponer formularios basados en modelos para CRUD en vistas/templates,
    con widgets mínimos y una validación defensiva en `ProductoForm.clean()`.

Responsabilidades:
    - ProveedorForm: CRUD directo sin personalizaciones.
    - ProductoForm: CRUD con placeholders y validación de precio/stock no negativos.

Diseño/Notas:
    - Se mantiene `fields="__all__"` mientras el modelo esté estable (iteración rápida).
    - No agregar labels/widgets para claves inexistentes (evita KeyError al renderizar).
"""

from django import forms
from .models import Proveedor, Producto


# ─────────────────────────────────────────────────────────────────────────────
# FORM: ProveedorForm
# Propósito: CRUD de Proveedor sin personalizaciones extra.
# ─────────────────────────────────────────────────────────────────────────────
class ProveedorForm(forms.ModelForm):
    """
    Formulario de Proveedor.

    Qué hace:
        - ModelForm directo para altas/ediciones/bajas en la UI admin/privada.

    Notas:
        - `fields="__all__"` permite evolución del modelo sin ajustar el form
        en cada cambio menor (si el modelo es estable).
    """
    class Meta:
        model = Proveedor
        fields = "__all__"


# ─────────────────────────────────────────────────────────────────────────────
# FORM: ProductoForm
# Propósito: CRUD de Producto con widgets básicos y validación defensiva.
# ─────────────────────────────────────────────────────────────────────────────
class ProductoForm(forms.ModelForm):
    """
    Formulario de Producto.

    Qué hace:
        - Exponer todos los campos del modelo (mientras esté estable).
        - Añadir placeholders mínimos para mejorar la UX de captura.
        - Validar que precio/stock no sean negativos (defensivo).

    Notas:
        - Evitar referenciar widgets/labels para campos que no existan realmente.
        Si el modelo cambia, ajustar aquí los nombres usados en `widgets` y `add_error`.
    """
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
            - precio_compra (o alias histórico `precio`) no puede ser negativo.
            - stock (o alias histórico `stock_inicial`) no puede ser negativo.

        Estrategia:
            - Se consultan primero los nombres “oficiales”; si no existen,
            se toleran alias históricos para compatibilidad.

        Returns:
            dict: cleaned_data validado.

        Side effects:
            - Usa `add_error(campo, mensaje)` en la clave correspondiente
            (si no existe el campo “oficial”, apunta al alias).
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