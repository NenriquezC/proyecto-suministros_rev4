from django.contrib import admin
from .models import Compra, CompraProducto

class CompraProductoInline(admin.TabularInline):
    model = CompraProducto
    extra = 0
    readonly_fields = ('total_linea',)  # para ver el total sin poder editarlo
    fields = ('producto', 'cantidad', 'precio_unitario', 'total_linea')
    show_change_link = True

@admin.register(Compra)
class CompraAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'proveedor', 'usuario', 'fecha',
        'subtotal', 'descuento_total', 'impuesto_total', 'total',
        'creado_en', 'actualizado_en'
    )
    list_filter = ('proveedor', 'usuario', 'fecha')
    search_fields = ('proveedor__nombre', 'usuario__username')
    inlines = [CompraProductoInline]
    readonly_fields = ('subtotal', 'descuento_total', 'impuesto_total', 'total', 'creado_en', 'actualizado_en')

@admin.register(CompraProducto)
class CompraProductoAdmin(admin.ModelAdmin):
    list_display = ('id', 'compra', 'producto', 'cantidad', 'precio_unitario', 'total_linea', 'creado_en')
    list_filter = ('producto', 'compra')
    search_fields = ('producto__nombre', 'compra__proveedor__nombre')
    readonly_fields = ('total_linea', 'creado_en')