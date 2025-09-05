from django.urls import path
from . import views

app_name = "compras"

urlpatterns = [
    path("", views.ver_compras, name="lista"),
    path("ver/", views.ver_compras, name="ver_compras"),   # alias opcional para listado
    path("<int:pk>/ver/", views.ver_compra, name="ver"),   # <── ESTE ES EL AJUSTE
    path("crear/", views.crear_compra, name="crear"),
    path("detalle/<int:pk>/", views.detalle_compra, name="detalle"),
    path("editar/<int:pk>/", views.editar_compra, name="editar"),
    path("eliminar/<int:pk>/", views.eliminar_compra, name="eliminar"),
    path("agregar/", views.crear_compra, name="agregar"),
]