
# compras/urls.py
"""
Rutas de la app 'compras'.

Mapa URL → Vista → Template (resumen)
- Listado: /compras/ver/                      → views.ver_compras → templates/compras/lista_compra/lista.html
- Detalle (solo lectura): /compras/detalle/<pk>/       → views.detalle_compra → templates/compras/editar_compra/editar_compra.html
- Ver (alias de detalle): /compras/ver/<pk>/           → views.ver_compra     → templates/compras/editar_compra/editar_compra.html
- Editar: /compras/editar/<pk>/                        → views.editar_compra  → templates/compras/editar_compra/editar_compra.html
- Eliminar: /compras/eliminar/<pk>/                    → views.eliminar_compra→ templates/compras/eliminar_confirm.html
- Agregar (crear): /compras/agregar/                   → views.crear_compra   → templates/compras/agregar_compra/agregar_compra.html

Nota:
- Si quieres exponer también /compras/crear/ y /compras/<pk>/ver/ (mencionadas en documentación previa),
puedes habilitarlas en la sección “Aliases opcionales” de abajo para mantener compatibilidad de URLs.
"""

from django.urls import path
from . import views

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