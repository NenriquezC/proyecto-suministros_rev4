# compras/admin.py
"""
Admin de la app 'compras'.

Responsabilidades:
- Configurar la visualización y edición de Compra y CompraProducto en el admin.
- Incluir un inline tabular para gestionar líneas desde la cabecera de compra.

Diseño:
- Campos calculados y de auditoría en solo lectura (evita ediciones accidentales).
- Listados con filtros y búsqueda para navegación rápida.
"""
from django.contrib import admin
from .models import Compra, CompraProducto


# ─────────────────────────────────────────────────────────────────────────────
# Inline de líneas de compra (detalle dentro de la cabecera)
# ─────────────────────────────────────────────────────────────────────────────
class CompraProductoInline(admin.TabularInline):
    """
    Inline tabular para editar/visualizar líneas (CompraProducto) dentro de Compra.

    Notas:
    - `extra=0` evita filas vacías no deseadas.
    - `total_linea` es de solo lectura (se calcula en el modelo).
    - `show_change_link=True` permite abrir la línea en su admin propio.
    """
    model = CompraProducto
    extra = 0
    readonly_fields = ('total_linea',)  # para ver el total sin poder editarlo
    fields = ('producto', 'cantidad', 'precio_unitario', 'total_linea')
    show_change_link = True

# ─────────────────────────────────────────────────────────────────────────────
# Admin de cabecera de compra
# ─────────────────────────────────────────────────────────────────────────────
@admin.register(Compra)
class CompraAdmin(admin.ModelAdmin):
    """
    Admin de la entidad Compra (cabecera).

    Objetivo:
    - Mostrar los campos clave (proveedor, usuario, fecha y totales).
    - Permitir filtrar y buscar de forma rápida.
    - Gestionar las líneas asociadas mediante inline tabular.

    Detalles:
    - `readonly_fields` asegura que los totales/auditoría no se editen a mano.
    - `inlines` incorpora `CompraProductoInline` para trabajar líneas en la misma vista.
    """
    list_display = (
        'id', 'proveedor', 'usuario', 'fecha',
        'subtotal', 'descuento_total', 'impuesto_total', 'total',
        'creado_en', 'actualizado_en'
    )
    list_filter = ('proveedor', 'usuario', 'fecha')
    search_fields = ('proveedor__nombre', 'usuario__username')
    inlines = [CompraProductoInline]
    readonly_fields = ('subtotal', 'descuento_total', 'impuesto_total', 'total', 'creado_en', 'actualizado_en')


# ─────────────────────────────────────────────────────────────────────────────
# Admin de líneas de compra (detalle independiente)
# ─────────────────────────────────────────────────────────────────────────────
@admin.register(CompraProducto)
class CompraProductoAdmin(admin.ModelAdmin):
    """
    Admin de la entidad CompraProducto (línea de compra).

    Objetivo:
    - Consultar rápidamente líneas por compra y por producto.
    - Evitar modificar el total calculado manualmente.

    Detalles:
    - `readonly_fields` protege `total_linea` y la fecha de creación.
    - `list_filter` facilita navegación por producto/compra.
    - `search_fields` permite buscar por nombre de producto y proveedor de la compra.
    """
    list_display = ('id', 'compra', 'producto', 'cantidad', 'precio_unitario', 'total_linea', 'creado_en')
    list_filter = ('producto', 'compra')
    search_fields = ('producto__nombre', 'compra__proveedor__nombre')
    readonly_fields = ('total_linea', 'creado_en')