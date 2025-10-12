# compras/models.py
"""
Modelos de la app 'compras'.

Responsabilidades:
- Representar la cabecera de una compra (Compra) y sus líneas (CompraProducto).
- Mantener restricciones de dominio a nivel de modelo/DB (validadores y constraints).
- Calcular total_linea en cada línea al guardar (persistencia de denormalizado útil).

Diseño:
- FK protegida a Proveedor y Usuario (no se pueden borrar si hay compras).
- Campos monetarios con Decimal y validadores >= 0 (consistencia de datos).
- Índices en campos de filtro frecuente (fecha, proveedor, usuario, compra, producto).
"""
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator

User = get_user_model()

# ─────────────────────────────────────────────────────────────────────────────
# Cabecera de compra
# ─────────────────────────────────────────────────────────────────────────────
class Compra(models.Model):
    """
    Cabecera de una compra.

    Campos:
        proveedor            FK → inventario.Proveedor (PROTECT)
        usuario              FK → auth.User (o custom), registra quién creó la compra
        fecha                Fecha/hora de la compra (default=timezone.now)
        subtotal             Suma de líneas (≥ 0)
        descuento_porcentaje Porcentaje 0..100 (entero pequeño)
        impuesto_total       Monto total de impuestos (≥ 0)
        descuento_total      Monto de descuentos (≥ 0)
        total                Total final (≥ 0)
        creado_en            Timestamp de creación (auto)
        actualizado_en       Timestamp de actualización (auto)

    Notas:
        - Los cálculos de subtotal/impuesto/total se hacen en services (fuente de verdad).
        - Aquí reforzamos límites mínimos para que la BD nunca reciba valores negativos.
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
        Metadatos de la tabla:
        - ordering: resultados recientes primero (fecha DESC, id DESC).
        - indexes: aceleran búsquedas por fecha, proveedor y usuario.
        """
        ordering = ['-fecha', '-id']
        indexes = [
            models.Index(fields=['fecha']),
            models.Index(fields=['proveedor']),
            models.Index(fields=['usuario']), 
        ]

    def __str__(self):
        return f"Compra {self.id} - {self.proveedor.nombre}"

# ─────────────────────────────────────────────────────────────────────────────
# Línea de compra
# ─────────────────────────────────────────────────────────────────────────────
class CompraProducto(models.Model):
    """
    Línea de una compra (detalle por producto).

    Campos:
        compra          FK → Compra (CASCADE)
        producto        FK → inventario.Producto (PROTECT)
        cantidad        > 0 (entero positivo)
        precio_unitario ≥ 0
        total_linea     cantidad * precio_unitario (2 decimales, se recalcula en save)
        creado_en       Timestamp de creación

    Notas:
        - Se incluyen constraints DB para reforzar reglas (>0 y ≥0).
        - total_linea se denormaliza para consultas/ordenaciones más rápidas.
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
        Metadatos de la tabla:
        - ordering: orden natural por id ascendente.
        - indexes: por compra y producto para listados/joins.
        - constraints: reglas a nivel DB (cantidad > 0, precio_unitario ≥ 0).
        - Ejemplo opcional (comentado) para evitar repetidos por compra+producto.
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