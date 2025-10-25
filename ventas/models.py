"""
Modelos de Ventas: Venta y VentaProducto.

Propósito:
    Representar la cabecera de una venta y sus líneas de detalle, con
    validaciones a nivel de modelo/BD e índices para consultas frecuentes.

Responsabilidades:
    - Venta: totales (subtotal, impuesto, descuento_total, total) y metadatos.
    - VentaProducto: líneas de detalle con precio, cantidad y % de descuento.

Diseño/Notas:
    - `impuesto_porcentaje` guarda el % que ingresó la UI (0..100); el importe
    `impuesto` se calcula en services (fuente de verdad).
    - Índices por fecha/cliente y por venta/producto para acelerar listados.
    - Constraints aseguran no negatividad y rangos válidos (0..100 en %).
"""
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator

User = get_user_model()

# ─────────────────────────────────────────────────────────────────────────────
# MODELO: Venta (cabecera)
# ─────────────────────────────────────────────────────────────────────────────
class Venta(models.Model):
    """
    Cabecera de una venta.

    Campos:
        cliente              FK → auth.User (o custom)
        fecha                Date (editable)
        subtotal             Σ líneas (≥ 0; se recalcula en services)
        impuesto             Importe de impuestos (≥ 0; calculado en services)
        impuesto_porcentaje  Porcentaje 0..100 ingresado desde la UI
        descuento_total      Importe absoluto de descuentos (≥ 0)
        total                Total final (≥ 0)
        creado_en/actualizado_en  timestamps

    Meta:
        - ordering: recientes primero (fecha DESC, id DESC).
        - indexes: por fecha y cliente (filtros típicos).
    """
    cliente = models.ForeignKey(User, on_delete=models.PROTECT, related_name='ventas')
    fecha = models.DateField(default=timezone.localdate)  # editable por el usuario si hace falta
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    impuesto = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    impuesto_porcentaje = models.DecimalField(max_digits=5,decimal_places=2,default=Decimal('0.00'),
    validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))])
    escuento_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'),validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))])
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


# ─────────────────────────────────────────────────────────────────────────────
# MODELO: VentaProducto (línea)
# ─────────────────────────────────────────────────────────────────────────────
class VentaProducto(models.Model):
    """
    Línea de detalle de una venta.

    Campos:
        venta           FK → Venta (CASCADE)
        producto        FK → inventario.Producto (PROTECT)
        cantidad        > 0 (entero positivo)
        precio_unitario ≥ 0
        descuento       % 0..100 por línea (opcional; default 0)
        creado_en       timestamp de creación

    Meta:
        - ordering natural por id.
        - indexes por venta y producto (joins habituales).
        - constraints:
            * cantidad > 0
            * precio_unitario ≥ 0
            * 0 ≤ descuento ≤ 100
        - (opcional, comentado) unique por (venta, producto).
    """
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