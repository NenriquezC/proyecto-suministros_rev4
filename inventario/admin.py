"""
Admin de la app Inventario.

Responsabilidades:
- Configurar la administración de Producto, Categoria y Proveedor.
- Proteger campos calculados/derivados en modo solo lectura.
- Ofrecer listados útiles (list_display) para navegación rápida.

Diseño:
- Sin cambios de lógica ni nombres; solo documentación estandarizada.
- `ProductoAdmin.get_readonly_fields` asegura que `stock_minimo` no se edite manualmente.
"""

from django.contrib import admin
from .models import Producto, Categoria, Proveedor


# ─────────────────────────────────────────────────────────────────────────────
# Admin: Producto
# ─────────────────────────────────────────────────────────────────────────────
class ProductoAdmin(admin.ModelAdmin):
    """
    Admin de Producto.

    Notas:
    - `stock_minimo` se calcula/ajusta vía lógica del modelo (save),
        por eso permanece en solo lectura en el admin.
    - `precio_venta_display` muestra el precio de venta en caso de usarse
        en list_display (aquí NO se agrega para no cambiar tu vista actual).
    """
    readonly_fields = ('stock_minimo',)
    list_display = ('nombre', 'descripcion','precio_compra', 'stock', 'stock_minimo','proveedor', 'categoria','ganancia', 'creado_en')
    #bloqueo de campos para que no se puedan editar (stock_minimo es readonly siempre)
    def get_readonly_fields(self, request, obj=None):
        # stock_minimo es readonly siempre
        return self.readonly_fields

    def precio_venta_display(self, obj): #Si quieres mostrar el precio de venta calculado:
        return obj.precio_compra * (1 + obj.ganancia / 100)

    precio_venta_display.short_description = 'Precio de Venta'


# ─────────────────────────────────────────────────────────────────────────────
# Admin: Categoria
# ─────────────────────────────────────────────────────────────────────────────
class CategoriaAdmin(admin.ModelAdmin):
    """Admin de Categoria (listado simple por nombre)."""
    list_display = ('nombre',)

# ─────────────────────────────────────────────────────────────────────────────
# Admin: Proveedor
# ─────────────────────────────────────────────────────────────────────────────
class ProveedorAdmin(admin.ModelAdmin):
    """Admin de Proveedor (campos básicos, ordenados para lectura rápida)."""
    list_display = ('nombre', 'direccion','telefono', 'tipo_proveedor',  'email', 'creado_en')


# ─────────────────────────────────────────────────────────────────────────────
# Registro de modelos
# ─────────────────────────────────────────────────────────────────────────────
admin.site.register(Producto, ProductoAdmin)
admin.site.register(Categoria, CategoriaAdmin)
admin.site.register(Proveedor, ProveedorAdmin)
