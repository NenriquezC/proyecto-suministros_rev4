from django.shortcuts import render

# Create your views here.
# inventario/views.py
from django.http import HttpResponse

def inventario(request):
    return HttpResponse("Inventário — em construção")

def agregar_producto(request):
    return HttpResponse("Agregar producto — em construção")

def editar_producto(request, pk):
    return HttpResponse(f"Editar producto {pk} — em construção")

def eliminar_producto(request, pk):
    return HttpResponse(f"Eliminar producto {pk} — em construção")

def listar_productos(request):
    return HttpResponse("Listado de productos — em construção")