
"""
Rutas del proyecto.

Decisiones:
- Home único en '/' usando suministros.views.index (contadores).
- Dashboard vive en '/dashboard/' vía su app.
- Cada app con su namespace para reverses claros.
"""

from django.contrib import admin
from django.urls import path, include
from . import views   # 👈 importa la vista index
from dashboard.views import index  # ← importa la vista

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    # Home global (con contexto dinámico de suministros/views.py)
    path("", views.index, name='home'),                 # ← http://127.0.0.1:8000/


    # Apps
    path("compras/", include(("compras.urls", "compras"), namespace="compras")),
    path('inventario/', include(('inventario.urls', 'inventario'), namespace='inventario')),
    path('ventas/', include(('ventas.urls', 'ventas'), namespace='ventas')),
    path("dashboard/", include(("dashboard.urls", "dashboard"), namespace="dashboard")),  

    # Auth (login/logout/password reset…)
    path("accounts/", include("django.contrib.auth.urls")), 

    
    

    

    


]
