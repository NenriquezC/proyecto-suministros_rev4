from django.http import HttpResponse

# ventas/views.py
from django.http import HttpResponse

def ver_ventas(request):
    return HttpResponse("Listado de ventas (WIP)")

def crear_venta(request):
    return HttpResponse("Crear venta (WIP)")

def detalle_venta(request, venta_id):
    return HttpResponse(f"Detalle venta {venta_id} (WIP)")

def editar_venta(request, venta_id):
    return HttpResponse(f"Editar venta {venta_id} (WIP)")

def eliminar_venta(request, venta_id):
    return HttpResponse(f"Eliminar venta {venta_id} (WIP)")