from django.urls import path
from django.contrib import admin
from .views import ver_compras, crear_compra, detalle_compra, editar_compra, eliminar_compra

app_name = 'compras'
urlpatterns = [
    
    path('admin/', admin.site.urls), 
    path('ver/', ver_compras, name='ver_compras'),
    path('agregar/', crear_compra, name='agregar_compra'),
    path('<int:pk>/', detalle_compra, name='detalle'),
    path('<int:pk>/editar/', editar_compra, name='editar'),
    path('<int:pk>/eliminar/', eliminar_compra, name='eliminar'),
]