from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
#============================================================================================================================================
class Categoria(models.Model):
    nombre = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

#============================================================================================================================================
class Proveedor(models.Model):
    nombre = models.CharField(max_length=150)
    direccion = models.CharField(max_length=255)
    telefono = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    tipo_proveedor = models.CharField(
        max_length=50,
        choices=[('empresa', 'Empresa'), ('particular', 'Particular')]
    )
    #rubro = models.CharField(max_length=100, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    #---------------------------------------------------------------------------------------------------------------------------------------------
    class Meta:
        ordering = ['nombre']
        # Si quieres evitar duplicados exactos:
        # constraints = [
        #     models.UniqueConstraint(fields=['nombre', 'telefono'], name='uniq_proveedor_nombre_telefono')
        # ]

    def __str__(self):
        return self.nombre

#============================================================================================================================================
class Producto(models.Model):
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True)
    precio_compra = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0'))])
    stock = models.PositiveIntegerField()
    stock_minimo = models.PositiveIntegerField(blank=True, null=True)
    proveedor = models.ForeignKey('Proveedor', on_delete=models.PROTECT, related_name='productos')
    categoria = models.ForeignKey('Categoria', on_delete=models.PROTECT, related_name='productos')
    ganancia = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        help_text="Porcentaje de ganancia sobre el precio de compra (ej: 20.00 para 20%)"
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    #---------------------------------------------------------------------------------------------------------------------------------------------
    class Meta:
        ordering = ['nombre']
        indexes = [
            models.Index(fields=['categoria']),
            models.Index(fields=['proveedor']),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(precio_compra__gte=0), name='precio_compra_gte_0'),
        ]
    #---------------------------------------------------------------------------------------------------------------------------------------------
    def save(self, *args, **kwargs):
        # al crearlo, define stock mínimo como 90% del stock inicial si no está seteado
        if not self.pk and self.stock is not None and self.stock_minimo is None:
            self.stock_minimo = int(self.stock * 0.9)
        super().save(*args, **kwargs) #Llama a super().save(*args, **kwargs) para ejecutar el método save original de Django y guardar el objeto en la base de datos.
    #---------------------------------------------------------------------------------------------------------------------------------------------
    @property
    def precio_venta(self):
        # precio_compra * (1 + ganancia/100)
        return (self.precio_compra * (Decimal('1') + (self.ganancia / Decimal('100')))).quantize(Decimal('0.01'))

    def __str__(self):
        return self.nombre
#============================================================================================================================================