from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.views.generic import TemplateView


urlpatterns = [
    path('admin/', admin.site.urls),

    # incluye las urls de la app compras
    path('compras/', include('compras.urls', namespace='compras')),
    path('ventas/', include('ventas.urls')),
    path('inventario/', include('inventario.urls')),
    # Home global (sin app)
    path('', TemplateView.as_view(template_name='index.html'), name='home'),


]

