# compras/models.py
"""
Modelos de la app 'compras'.

Propósito:
    Representar la cabecera de una compra (Compra) y sus líneas (CompraProducto),
    reforzando reglas de dominio a nivel de modelo y base de datos (validadores,
    constraints e índices) y conservando un denormalizado útil (total_linea).

Responsabilidades:
    - Compra: datos de cabecera (proveedor, usuario, fecha y totales).
    - CompraProducto: líneas de detalle con cantidad, precio y total_linea.
    - Persistencia de reglas mínimas: no negativos, porcentajes 0..100, etc.
    - Índices en campos de consulta frecuente.

Dependencias/Assume:
    - inventario.Proveedor y inventario.Producto existen y están íntegros.
    - El cálculo de subtotal/impuestos/total se realiza en services/modelos
    (fuente de la verdad), no en estos modelos.
    - Django usa Decimal para importes monetarios.

Diseño/UX/Datos:
    - on_delete=PROTECT en proveedor/usuario: evita borrar maestros con compras.
    - Campos monetarios como Decimal (max_digits=12, decimal_places=2).
    - Índices en fecha/proveedor/usuario/compra/producto para acelerar listados.
    - total_linea se guarda (denormalizado) para ordenar/filtrar rápido.

Notas:
    - No se cambia comportamiento ni nombres. Solo documentación y comentarios.
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
        proveedor (FK, PROTECT): no permite borrar proveedor con compras asociadas.
        usuario   (FK, PROTECT): quién registró la compra; evita borrado si hay trazas.
        fecha     (DateTime): cuándo ocurrió la compra (default=timezone.now).
        subtotal  (Decimal ≥ 0): suma de líneas antes de descuentos/impuestos.
        descuento_porcentaje (0..100): porcentaje global aplicado a la base.
        impuesto_total (Decimal ≥ 0): monto de impuestos (no el %).
        descuento_total (Decimal ≥ 0): monto total descontado en dinero.
        total     (Decimal ≥ 0): importe final (base - descuento + impuesto).
        creado_en / actualizado_en: auditoría temporal.

    Invariantes:
        - Todos los importes monetarios son no negativos.
        - descuento_porcentaje ∈ [0, 100].

    Notas:
        - El cálculo de la aritmética (subtotal, descuento_total, impuesto_total y total)
        se delega a services/modelos, para mantener una única fuente de verdad.
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
        """Representación legible: 'Compra <id> - <proveedor>'."""
        return f"Compra {self.id} - {self.proveedor.nombre}"

# ─────────────────────────────────────────────────────────────────────────────
# Línea de compra
# ─────────────────────────────────────────────────────────────────────────────
class CompraProducto(models.Model):
    """
    Línea de una compra (detalle por producto).

    Campos:
        compra          (FK, CASCADE): si se borra la compra, caen sus líneas.
        producto        (FK, PROTECT): no se permite borrar productos con compras.
        cantidad        (int > 0): unidades compradas.
        precio_unitario (Decimal ≥ 0): precio por unidad en el momento de la compra.
        total_linea     (Decimal ≥ 0): cantidad * precio_unitario (denormalizado).
        creado_en       (auto): timestamp de creación de la línea.

    Reglas/Constraints:
        - cantidad > 0 (CheckConstraint DB) y validator de campo.
        - precio_unitario ≥ 0 (CheckConstraint DB) y validator de campo.

    Rendimiento:
        - Índices en compra y producto para joins/listados frecuentes.
        - Guardar total_linea acelera ordenamiento/filtrado y reportes.

    Notas:
        - El redondeo a 2 decimales se mantiene al guardar, usando Decimal.quantize()
        con el contexto por defecto de Decimal (sin alterar tu comportamiento actual).
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
            - ordering: orden natural por id ascendente (mantiene inserción).
            - indexes: por compra y producto para listados/joins.
            - constraints:
                * cantidad > 0
                * precio_unitario ≥ 0
            - (Opcional) UniqueConstraint compra+producto si se quisiera evitar duplicados.
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
        """
        Calcula y persiste total_linea como cantidad * precio_unitario (2 decimales).

        Notas:
            - Se mantiene el contexto/rounding por defecto de Decimal.quantize()
            (no se cambia comportamiento). Si en el futuro necesitas un modo
            de redondeo específico (p.ej., ROUND_HALF_UP), defínelo en services
            para aplicar coherencia global.

        Side-effects:
            - Actualiza total_linea antes de guardar.
        """
        self.total_linea = (self.cantidad * self.precio_unitario).quantize(Decimal('0.01'))
        super().save(*args, **kwargs)



    def __str__(self):
        """Representación legible: '<producto> x <cantidad> en compra #<id>'."""
        return f"{self.producto.nombre} x {self.cantidad} en compra #{self.compra.id}"