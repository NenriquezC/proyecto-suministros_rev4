from django.contrib import admin
from .models import Venta, VentaProducto

# Register your models here.
class VentaAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'fecha', 'impuesto', 'descuento_total', 'total', 'creado_en', 'actualizado_en')

class Venta_ProductoAdmin(admin.ModelAdmin):
    list_display = ('venta', 'producto', 'cantidad', 'precio_unitario','descuento', 'creado_en')

admin.site.register(Venta, VentaAdmin)
admin.site.register(VentaProducto, Venta_ProductoAdmin)
