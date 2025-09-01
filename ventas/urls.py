from django.urls import path
from .  import views

app_name = 'ventas'
urlpatterns = [
    path('ver/', views.ver_ventas, name='ver_ventas'),
    path('crear/', views.crear_venta, name='crear_venta'),
    path('<int:venta_id>/', views.detalle_venta, name='detalle_venta'),
    path('<int:venta_id>/editar/', views.editar_venta, name='editar_venta'),
    path('<int:venta_id>/eliminar/', views.eliminar_venta, name='eliminar_venta'),
]