"""
URLs del módulo Inventario.

Responsabilidades:
- Exponer rutas para Productos y Proveedores (CRUD, ver/detalle).
- Publicar endpoint JSON para precio de producto.

Diseño:
- Namespace propio (`app_name = "inventario"`) para evitar colisiones.
- Agrupar por recurso y usar paths legibles.
- Mantener alias de compatibilidad donde aplica (detalle_producto → ver_producto).
"""

from django.urls import path
from . import views

app_name = "inventario"



urlpatterns = [
    # ─────────────────────────────────────────────────────────────────────────
    # HOME INVENTARIO
    # GET /inventario/ → redirige a una vista existente (proveedores o productos)
    # ─────────────────────────────────────────────────────────────────────────
    path("", views.inventario, name="inventario"),

    # ─────────────────────────────────────────────────────────────────────────
    # PRODUCTOS
    # ─────────────────────────────────────────────────────────────────────────
    path("producto/", views.listar_productos, name="listar_productos"),
    path("producto/agregar/", views.agregar_producto, name="agregar_producto"),
    path("producto/editar/<int:pk>/", views.editar_producto, name="editar_producto"),
    path("producto/eliminar/<int:pk>/", views.eliminar_producto, name="eliminar_producto"),

    # Lectura/Detalle
    path("producto/ver/<int:pk>/", views.ver_producto, name="ver_producto"),
    path("producto/detalle/<int:pk>/", views.ver_producto, name="detalle_producto"),  # alias opcional

    # API JSON (precio por producto)
    path("api/producto/<int:pk>/precio/", views.producto_precio_api, name="producto_precio"),

    
    

    # ─────────────────────────────────────────────────────────────────────────
    # PROVEEDORES
    # ─────────────────────────────────────────────────────────────────────────
    path("proveedores/", views.listar_proveedores, name="listar_proveedores"),
    path("proveedores/nuevo/", views.agregar_proveedor, name="agregar_proveedor"),
    path("proveedores/<int:pk>/editar/", views.editar_proveedor, name="editar_proveedor"),
    path("proveedores/<int:pk>/eliminar/", views.eliminar_proveedor, name="eliminar_proveedor"),
    path("proveedores/nuevo/", views.proveedor_crear, name="proveedor_crear"),

    # Lectura/Detalle
    path("proveedores/<int:pk>/", views.ver_proveedor, name="ver_proveedor"),

]
