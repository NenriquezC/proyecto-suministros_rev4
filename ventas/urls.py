# ventas/urls.py
from django.urls import path
from . import views

app_name = "ventas"

urlpatterns = [
    # LISTADO
    path("ver/", views.ver_ventas, name="ver_ventas"),

    # DETALLE / VER (solo lectura)
    path("detalle/<int:pk>/", views.ver_venta, name="detalle"),   # alias usado por redirects
    path("ver/<int:pk>/",      views.ver_venta, name="ver_venta"),

    # EDITAR
    path("editar/<int:pk>/", views.editar_venta, name="editar_venta"),

    # ELIMINAR
    path("eliminar/<int:pk>/", views.eliminar_venta, name="eliminar_venta"),

    # AGREGAR (crear)
    path("agregar/", views.crear_venta, name="agregar_venta"),
]