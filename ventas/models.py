from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator

User = get_user_model()

class Venta(models.Model):
    cliente = models.ForeignKey(User, on_delete=models.PROTECT, related_name='ventas')
    fecha = models.DateField(default=timezone.localdate)  # editable por el usuario si hace falta
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    impuesto = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    impuesto_porcentaje = models.DecimalField(max_digits=5,decimal_places=2,default=Decimal('0.00'),
    validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))]
)
    descuento_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fecha', '-id']
        indexes = [
            models.Index(fields=['fecha']),
            models.Index(fields=['cliente']),
        ]

    def __str__(self):
        return f"Venta {self.id} - {self.cliente.username}"


class VentaProducto(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey('inventario.Producto', on_delete=models.PROTECT, related_name='ventas')
    cantidad = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0'))])
    # Opción: porcentaje de descuento por línea (0–100)
    descuento = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'),
                                    validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))])
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']
        indexes = [
            models.Index(fields=['venta']),
            models.Index(fields=['producto']),
        ]
        # Si NO quieres el mismo producto repetido en la misma venta:
        # constraints = [
        #     models.UniqueConstraint(fields=['venta', 'producto'], name='uniq_venta_producto')
        # ]
        constraints = [
            models.CheckConstraint(check=models.Q(cantidad__gt=0), name='venta_cantidad_gt_0'),
            models.CheckConstraint(check=models.Q(precio_unitario__gte=0), name='venta_precio_unitario_gte_0'),
            models.CheckConstraint(check=models.Q(descuento__gte=0) & models.Q(descuento__lte=100),
                                name='venta_descuento_0_100'),
        ]

    def __str__(self):
        return f"{self.producto.nombre} x {self.cantidad} en venta #{self.venta.id}"