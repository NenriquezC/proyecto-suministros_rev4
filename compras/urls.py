# compras/urls.py
from django.urls import path
from . import views

app_name = "compras"

urlpatterns = [
    # LISTA (tu view existente)
    path("", views.ver_compras, name="lista"),
    path("ver/", views.ver_compras, name="ver_compras"),  # si ya lo usas en algún lado
    # CREAR
    path("crear/", views.crear_compra, name="crear"),
    # DETALLE
    path("detalle/<int:pk>/", views.detalle_compra, name="detalle"),
    # EDITAR (siempre con pk)
    path("editar/<int:pk>/", views.editar_compra, name="editar"),
    # ELIMINAR (siempre con pk)
    path("eliminar/<int:pk>/", views.eliminar_compra, name="eliminar"),
    # ⬇️ ALIAS ADITIVO para que el template pueda usar 'compras:agregar'
    path("agregar/", views.crear_compra, name="agregar"),
]