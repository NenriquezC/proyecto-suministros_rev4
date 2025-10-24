"""
Admin de la app Inventario.

Propósito:
    Configurar la interfaz de administración para Producto, Categoria y Proveedor,
    priorizando campos útiles en list_display y protegiendo los derivados.

Responsabilidades:
    - ProductoAdmin: lectura de campos calculados/derivados (stock_minimo).
    - CategoriaAdmin: listado simple por nombre.
    - ProveedorAdmin: listado de datos de contacto y clasificación.

Diseño/Notas:
    - Sin cambios de lógica ni nombres; solo documentación estandarizada.
    - ProductoAdmin.get_readonly_fields mantiene `stock_minimo` en solo lectura
    (se calcula en capa de dominio/servicios).
"""

from django.contrib import admin
from .models import Producto, Categoria, Proveedor


# ─────────────────────────────────────────────────────────────────────────────
# Admin: Producto
# ─────────────────────────────────────────────────────────────────────────────
class ProductoAdmin(admin.ModelAdmin):
    """
    Admin de Producto.

    Qué muestra:
        - list_display: columnas clave para inspección rápida (precio_compra, stock,
        stock_minimo, proveedor, categoria, ganancia, creado_en).

    Protección:
        - `stock_minimo` se considera derivado/ajustado por lógica del dominio (e.g.,
        reglas al crear compras). Por eso permanece en solo lectura en el admin.

    Notas:
        - `precio_venta_display` disponible como helper si quisieras incluirlo en
        list_display (no se agrega aquí para no cambiar tu UI actual).
    """
    readonly_fields = ('stock_minimo',)
    list_display = ('nombre', 'descripcion','precio_compra', 'stock', 'stock_minimo','proveedor', 'categoria','ganancia', 'creado_en')
    #bloqueo de campos para que no se puedan editar (stock_minimo es readonly siempre)
    def get_readonly_fields(self, request, obj=None):
        """
        Define campos de solo lectura en la UI del admin.

        Regla:
            - `stock_minimo` siempre readonly (evita edición manual).
        """
        # stock_minimo es readonly siempre
        return self.readonly_fields

    def precio_venta_display(self, obj): #Si quieres mostrar el precio de venta calculado:
        """
        (Opcional) Precio de venta calculado a partir de `precio_compra` y `ganancia`.

        Retorna:
            Decimal/float: precio calculado.
        """
        return obj.precio_compra * (1 + obj.ganancia / 100)

    precio_venta_display.short_description = 'Precio de Venta'


# ─────────────────────────────────────────────────────────────────────────────
# Admin: Categoria
# ─────────────────────────────────────────────────────────────────────────────
class CategoriaAdmin(admin.ModelAdmin):
    """
    Admin de Categoria.

    Qué muestra:
        - list_display: nombre (orden y filtrado estándar de Django).
    """
    list_display = ('nombre',)

# ─────────────────────────────────────────────────────────────────────────────
# Admin: Proveedor
# ─────────────────────────────────────────────────────────────────────────────
class ProveedorAdmin(admin.ModelAdmin):
    """
    Admin de Proveedor.

    Qué muestra:
        - list_display: nombre, dirección, teléfono, tipo_proveedor, email, creado_en
        para navegación y verificación rápida de datos de contacto.
    """
    list_display = ('nombre', 'direccion','telefono', 'tipo_proveedor',  'email', 'creado_en')


# ─────────────────────────────────────────────────────────────────────────────
# Registro de modelos
# ─────────────────────────────────────────────────────────────────────────────
admin.site.register(Producto, ProductoAdmin)
admin.site.register(Categoria, CategoriaAdmin)
admin.site.register(Proveedor, ProveedorAdmin)
