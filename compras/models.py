from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator

User = get_user_model()

class Compra(models.Model):
    """
    Modelo de la tabla "compras". Se relaciona con la tabla "proveedores" y "usuarios".
    atributos: proveedor, usuario, fecha, subtotal, impuesto, descuento_total, total, creado_en, actualizado_en

    """
    proveedor = models.ForeignKey('inventario.Proveedor', on_delete=models.PROTECT, related_name='compras')
    usuario = models.ForeignKey(User, on_delete=models.PROTECT, related_name='compras_registradas')
    fecha = models.DateTimeField(default=timezone.now)
    #Es una validación a nivel Django (antes de grabar en DB). MinValueValidator(0) asegura que el valor nunca sea negativo.
    #Si alguien intenta guardar -50.00, Django lanza un ValidationError.
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'),validators=[MinValueValidator(Decimal('0'))])
    descuento_porcentaje = models.PositiveSmallIntegerField(default=0,validators=[MinValueValidator(0), MaxValueValidator(100)])
    impuesto_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'),validators=[MinValueValidator(Decimal('0'))])
    descuento_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'),validators=[MinValueValidator(Decimal('0'))])
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'),validators=[MinValueValidator(Decimal('0'))])
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    class Meta: 
        """
        Metodo de clase para definir el orden de los registros y las claves únicas.
        Clave única: compra_id
        Orden: fecha, id
        Índices: fecha, proveedor, usuario
        
        """
        ordering = ['-fecha', '-id']
        indexes = [
            models.Index(fields=['fecha']),
            models.Index(fields=['proveedor']),
            models.Index(fields=['usuario']), 
        ]

    def __str__(self):
        return f"Compra {self.id} - {self.proveedor.nombre}"


class CompraProducto(models.Model):
    """
    Modelo de la tabla "compras_productos". Se relaciona con la tabla "compras" y "productos".
    atributos: compra, producto, cantidad, precio_unitario, descuento, creado_en
    
    """
    compra = models.ForeignKey(Compra, on_delete=models.CASCADE, related_name='lineas')
    producto = models.ForeignKey('inventario.Producto', on_delete=models.PROTECT, related_name='compras')
    cantidad = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2,
                                        validators=[MinValueValidator(Decimal('0'))])
    total_linea = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'),
                                    validators=[MinValueValidator(Decimal('0'))])
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        """
        Metodo para ordenar por id y para generar un índice en la tabla.
        El método ordering ordena por el campo id en orden descendente. 
        El método indexes genera un índice en la tabla para el campo compra y producto.
        
        """
        ordering = ['id']
        indexes = [
            models.Index(fields=['compra']),
            models.Index(fields=['producto']),
        ]
        # Si no quieres repetidos por compra:
        # constraints = [
        #     models.UniqueConstraint(fields=['compra', 'producto'], name='uniq_compra_producto')
        # ]
        constraints = [
            models.CheckConstraint(check=models.Q(cantidad__gt=0), name='compra_cantidad_gt_0'),
            models.CheckConstraint(check=models.Q(precio_unitario__gte=0), name='compra_precio_unitario_gte_0'),
        ]
        
    def save(self, *args, **kwargs):
        self.total_linea = (self.cantidad * self.precio_unitario).quantize(Decimal('0.01'))
        super().save(*args, **kwargs)



    def __str__(self):
        return f"{self.producto.nombre} x {self.cantidad} en compra #{self.compra.id}"