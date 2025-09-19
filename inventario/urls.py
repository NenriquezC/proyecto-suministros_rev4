from django.urls import path
from . import views

app_name = "inventario"



urlpatterns = [
    #path('', views.index, name='index'),
    #path('', views.inicio, name='inicio'),
    #path('inventario/', views.inventario, name='inventario'),

    # PRODUCTOS
    #path('agregar_producto/', views.agregar_producto, name='agregar_producto'), #para poder agreasr producto desde compra
    #path('producto/agregar/', views.agregar_producto, name='agregar_producto'),
    #path('producto/seleccionar_editar/', views.seleccionar_editar_producto, name='seleccionar_editar_producto'),
    #path('producto/editar/<int:pk>/', views.editar_producto, name='editar_producto'),
    #path('productos/seleccionar_eliminar/', views.seleccionar_eliminar_producto, name='seleccionar_eliminar_producto'),
    #path('producto/eliminar/<int:producto_id>/', views.eliminar_producto, name='eliminar_producto'),

    # PROVEEDORES
    #path('proveedor/agregar/', views.agregar_proveedor, name='agregar_proveedor'),
    #path('proveedor/editar/<int:proveedor_id>/', views.editar_proveedor, name='editar_proveedor'),
    # Para lista y buscar proveedor antes de editar
    #path('proveedor/editar/', views.seleccionar_editar_proveedor, name='seleccionar_editar_proveedor'),
    #path('proveedor/eliminar/', views.seleccionar_eliminar_proveedor, name='seleccionar_eliminar_proveedor'),
    #path('proveedor/eliminar/<int:proveedor_id>/', views.eliminar_proveedor, name='eliminar_proveedor'),
    #path('proveedor/eliminar/', views.lista_eliminar_proveedor, name='lista_eliminar_proveedor'), #agregado para eliminar proveedores desde el menu

    path("", views.inventario, name="inventario"),
    path("producto/", views.listar_productos, name="listar_productos"),
    path("producto/agregar/", views.agregar_producto, name="agregar_producto"),
    path("producto/editar/<int:pk>/", views.editar_producto, name="editar_producto"),
    path("producto/eliminar/<int:pk>/", views.eliminar_producto, name="eliminar_producto"),
    path("proveedores/nuevo/", views.proveedor_crear, name="proveedor_crear"),  # NUEVO
    #para hacer la peticion que hara el front aqui para obtener el valor del precio unitarioo
    path("api/producto/<int:pk>/precio/", views.producto_precio_api, name="producto_precio"),





]





