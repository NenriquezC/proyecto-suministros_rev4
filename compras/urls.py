from django.urls import path
from . import views

app_name = "compras"

urlpatterns = [
    #path("", views.ver_compras, name="lista"),
    path("ver/", views.ver_compras, name="ver_compras"),
    path("detalle/<int:pk>/", views.detalle_compra, name="detalle"),
    path("ver/<int:pk>/", views.ver_compra, name="ver_compra"),
    path("editar/<int:pk>/", views.editar_compra, name="editar_compra"),
    path("eliminar/<int:pk>/", views.eliminar_compra, name="eliminar_compra"),
    path("agregar/", views.crear_compra, name="agregar_compra"),
    # alias opcional para listado
    path("<int:pk>/ver/", views.ver_compra, name="ver"),   # <── ESTE ES EL AJUSTE
    path("crear/", views.crear_compra, name="crear"),
    
    
]