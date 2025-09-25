from django.urls import path
from . import views

app_name = "inventario"



urlpatterns = [
    path("", views.inventario, name="inventario"),
    path("producto/", views.listar_productos, name="listar_productos"),
    path("producto/agregar/", views.agregar_producto, name="agregar_producto"),
    path("producto/editar/<int:pk>/", views.editar_producto, name="editar_producto"),
    path("producto/eliminar/<int:pk>/", views.eliminar_producto, name="eliminar_producto"),
    #path("producto/nuevo/", views.producto_crear, name="producto_crear"),  # ← NUEVO (creación rápida con ?next)
    path("proveedores/nuevo/", views.proveedor_crear, name="proveedor_crear"),
    path("api/producto/<int:pk>/precio/", views.producto_precio_api, name="producto_precio"),

    path("producto/ver/<int:pk>/", views.ver_producto, name="ver_producto"),
    path("producto/detalle/<int:pk>/", views.ver_producto, name="detalle_producto"),  # alias opcional
]
