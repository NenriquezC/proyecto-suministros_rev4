from django.contrib import admin
from django.urls import path, include
from . import views   # 👈 importa la vista index

urlpatterns = [
    path('admin/', admin.site.urls),

    path("compras/", include(("compras.urls", "compras"), namespace="compras")),
    path('ventas/', include('ventas.urls')),
    path('inventario/', include(('inventario.urls', 'inventario'), namespace='inventario')),

    path("accounts/", include("django.contrib.auth.urls")),  # <- clave

    # Home global (con lógica y contexto dinámico)
    path('', views.index, name='home'),
]
