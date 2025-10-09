from django.contrib import admin
from django.urls import path, include
from . import views   # 👈 importa la vista index
from dashboard.views import index  # ← importa la vista

urlpatterns = [
    path('admin/', admin.site.urls),

    path("", index, name="home"),                 # ← http://127.0.0.1:8000/

    path("compras/", include(("compras.urls", "compras"), namespace="compras")),
    #path('ventas/', include('ventas.urls')),
    path('inventario/', include(('inventario.urls', 'inventario'), namespace='inventario')),

    path("accounts/", include("django.contrib.auth.urls")),  # <- clave

    # Home global (con lógica y contexto dinámico)
    path('', views.index, name='home'),

    path('ventas/', include(('ventas.urls', 'ventas'), namespace='ventas')),

    path("dashboard/", include(("dashboard.urls", "dashboard"), namespace="dashboard")),  # 👈 nuevo


]
