from django.urls import path
from . import views

app_name = 'ventas'
urlpatterns = [
    path("", views.ver_ventas, name="listar_ventas"),
    path("nuevo/", views.agregar_venta, name="agregar_venta"),
    path("<int:pk>/", views.ver_venta, name="ver_venta"),
    path("<int:pk>/editar/", views.editar_venta, name="editar_venta"),
    path("<int:pk>/eliminar/", views.eliminar_venta, name="eliminar_venta"),
]