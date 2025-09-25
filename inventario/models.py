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
        """
        Buenísimo. Eso es un paquete de reglas a nivel de base de datos (DB) que Django traducirá a CHECK CONSTRAINTS en la tabla de Producto.
        Se evalúan en cada INSERT/UPDATE. Si alguna no se cumple, la BD rechaza la operación (Django levanta IntegrityError). Una por una:
        precio_compra_gte_0
            Qué exige: precio_compra ≥ 0.
            Evita: precios negativos por error (p. ej., -10.00).
            Cuándo falla: crear/editar un producto con precio_compra < 0.
        producto_stock_gte_0
            Qué exige: stock ≥ 0.
            Evita: stock negativo.
            Cuándo falla: guardar stock = -1.
        producto_stock_minimo_gte_0_or_null
            Qué exige: stock_minimo ≥ 0 o stock_minimo IS NULL.
            Evita: valores negativos en stock_minimo.
            Permite: NULL cuando aún no has definido el mínimo (útil si lo calculas en save() al crear).
        Cuándo falla: stock_minimo = -5.
            producto_stock_minimo_lte_stock_or_null
            Qué exige: stock_minimo ≤ stock o stock_minimo IS NULL.
            Evita: mínimos imposibles (que el mínimo supere el stock actual).
            Cuándo falla: stock = 20 y stock_minimo = 25.
        """
        constraints = [
            models.CheckConstraint(check=models.Q(precio_compra__gte=0), name='precio_compra_gte_0'),
            models.CheckConstraint(check=models.Q(stock__gte=0), name='producto_stock_gte_0'),
            models.CheckConstraint(
                check=models.Q(stock_minimo__gte=0) | models.Q(stock_minimo__isnull=True),
                name='producto_stock_minimo_gte_0_or_null'
                ),
            models.CheckConstraint(
                check=models.Q(stock_minimo__lte=models.F('stock')) | models.Q(stock_minimo__isnull=True),
                name='producto_stock_minimo_lte_stock_or_null'
                ),
        ]
    #---------------------------------------------------------------------------------------------------------------------------------------------
    def save(self, *args, **kwargs):
        """
    Al crear el producto, si no se especifica stock_minimo,
    fijarlo como floor(0.9 * stock).
    """
        if not self.pk and self.stock is not None and self.stock_minimo is None:
            # floor(0.9 * stock) con aritmética entera
            self.stock_minimo = int(self.stock * 9) // 10 # = floor(0.9 * stock)
        super().save(*args, **kwargs) #Llama a super().save(*args, **kwargs) para ejecutar el método save original de Django y guardar el objeto en la base de datos.
    #---------------------------------------------------------------------------------------------------------------------------------------------
    @property
    def precio_venta(self):
        # precio_compra * (1 + ganancia/100)
        return (self.precio_compra * (Decimal('1') + (self.ganancia / Decimal('100')))).quantize(Decimal('0.01'))

    def __str__(self):
        return self.nombre
#============================================================================================================================================