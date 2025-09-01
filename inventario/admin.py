from django.contrib import admin
from .models import Producto, Categoria, Proveedor

# Register your models here.

#¿Por qué debe ser una clase?
#Django usa el patrón de clases para configurar opciones avanzadas y comportamientos personalizados para cada modelo en el admin.
#Al heredar de admin.ModelAdmin, puedes definir atributos (como list_display, search_fields, list_filter, etc.) y métodos para controlar exactamente cómo se administra el modelo.

class ProductoAdmin(admin.ModelAdmin):
    readonly_fields = ('stock_minimo',)
    list_display = ('nombre', 'descripcion','precio_compra', 'stock', 'stock_minimo','proveedor', 'categoria','ganancia', 'creado_en')
    #bloqueo de campos para que no se puedan editar (stock_minimo es readonly siempre)
    def get_readonly_fields(self, request, obj=None):
        # stock_minimo es readonly siempre
        return self.readonly_fields

    def precio_venta_display(self, obj): #Si quieres mostrar el precio de venta calculado:
        return obj.precio_compra * (1 + obj.ganancia / 100)

    precio_venta_display.short_description = 'Precio de Venta'

class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre',)


class ProveedorAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'direccion','telefono', 'tipo_proveedor',  'email', 'creado_en')



admin.site.register(Producto, ProductoAdmin)
admin.site.register(Categoria, CategoriaAdmin)
admin.site.register(Proveedor, ProveedorAdmin)
