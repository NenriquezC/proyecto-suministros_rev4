from django.urls import path
from . import views
"""
Rutas de la app 'compras'

Mapa URL → Vista → Template

Listado (plural)
- /compras/ver/                      (name="ver_compras")
    → views.ver_compras
    → templates/compras/lista_compra/lista.html

Detalle (solo lectura)
- /compras/detalle/<pk>/             (name="detalle")
    → views.detalle_compra
    → templates/compras/editar_compra/editar_compra.html (readonly=True)

Ver (alias de detalle, solo lectura)
- /compras/ver/<pk>/                 (name="ver_compra")
- /compras/<pk>/ver/                 (name="ver")
    → views.ver_compra
    → templates/compras/editar_compra/editar_compra.html (readonly=True)

Editar
- /compras/editar/<pk>/              (name="editar_compra")
    → views.editar_compra
    → templates/compras/editar_compra/editar_compra.html (readonly=False)

Agregar (crear)
- /compras/agregar/                  (name="agregar_compra")
- /compras/crear/                    (name="crear")
    → views.crear_compra
    → templates/compras/agregar_compra/agregar_compra.html

Eliminar
- /compras/eliminar/<pk>/            (name="eliminar_compra")
    → views.eliminar_compra
    → templates/compras/eliminar_confirm.html
"""
app_name = "compras"

urlpatterns = [
    # ────────────────────────────────
    # LISTADO DE COMPRAS
    # /compras/ver/
    # Muestra todas las compras en tabla con filtros y paginación.
    # Template: templates/compras/lista_compra/lista.html
    # ────────────────────────────────
    path("ver/", views.ver_compras, name="ver_compras"),

    # ────────────────────────────────
    # DETALLE DE COMPRA (SOLO LECTURA)
    # /compras/detalle/<pk>/
    # Reutiliza editar_compra.html pero con readonly=True.
    # Template: templates/compras/editar_compra/editar_compra.html
    # ────────────────────────────────
    path("detalle/<int:pk>/", views.detalle_compra, name="detalle"),

    # ────────────────────────────────
    # VER COMPRA (ALIAS SEMÁNTICO DE DETALLE)
    # /compras/ver/<pk>/
    # Igual que detalle_compra: reutiliza editar_compra.html (readonly=True).
    # Se mantiene por claridad semántica ("ver" en lugar de "detalle").
    # ────────────────────────────────
    path("ver/<int:pk>/", views.ver_compra, name="ver_compra"),

    # ────────────────────────────────
    # EDITAR COMPRA
    # /compras/editar/<pk>/
    # Permite modificar la cabecera y líneas de una compra existente.
    # Template: templates/compras/editar_compra/editar_compra.html
    # ────────────────────────────────
    path("editar/<int:pk>/", views.editar_compra, name="editar_compra"),

    # ────────────────────────────────
    # ELIMINAR COMPRA
    # /compras/eliminar/<pk>/
    # Muestra pantalla de confirmación y elimina la compra.
    # Template: templates/compras/eliminar_confirm.html
    # ────────────────────────────────
    path("eliminar/<int:pk>/", views.eliminar_compra, name="eliminar_compra"),

    # ────────────────────────────────
    # CREAR COMPRA
    # /compras/agregar/
    # Formulario para registrar nueva compra con cabecera + líneas.
    # Template: templates/compras/agregar_compra/agregar_compra.html
    # ────────────────────────────────
    path("agregar/", views.crear_compra, name="agregar_compra"),
]