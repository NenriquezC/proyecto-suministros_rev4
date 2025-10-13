
"""
URLs del módulo Dashboard.

Responsabilidades:
- Exponer las rutas del panel principal.

Diseño:
- Namespace propio (`app_name = "dashboard"`) para evitar colisiones.
- Mantener rutas simples y legibles.
"""

# dashboard/urls.py
from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.panel, name="panel"),
]