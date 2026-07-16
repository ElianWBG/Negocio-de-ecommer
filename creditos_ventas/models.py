from django.db import models

from billing.models import Invoice


class CuotaVenta(models.Model):
    """Una cuota del cronograma de pagos de una factura de venta a crédito."""

    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('pagada', 'Pagada'),
    ]

    factura = models.ForeignKey(
        Invoice, on_delete=models.PROTECT, related_name='cuotas',
        verbose_name='Factura',
    )
    numero = models.PositiveIntegerField(verbose_name='N° de cuota')
    fecha_vencimiento = models.DateField(verbose_name='Fecha de vencimiento')
    valor = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Valor de la cuota')
    saldo = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Saldo pendiente')
    estado = models.CharField(
        max_length=15, choices=ESTADO_CHOICES, default='pendiente',
        verbose_name='Estado',
    )

    class Meta:
        verbose_name = 'Cuota de venta'
        verbose_name_plural = 'Cuotas de venta'
        ordering = ['factura', 'numero']
        constraints = [
            models.UniqueConstraint(
                fields=['factura', 'numero'], name='unique_factura_numero_cuota',
            )
        ]

    def __str__(self):
        return f'Cuota {self.numero} - Factura #{self.factura_id}'


class PagoCuotaVenta(models.Model):
    """Registro de un abono realizado sobre una cuota de una factura de venta
    a crédito. Una cuota puede recibir múltiples pagos parciales hasta
    cancelarse."""

    cuota = models.ForeignKey(
        CuotaVenta, on_delete=models.PROTECT, related_name='pagos',
        verbose_name='Cuota',
    )
    fecha = models.DateField(verbose_name='Fecha de pago')
    valor = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Valor abonado')
    observacion = models.TextField(blank=True, verbose_name='Observación')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Pago de cuota de venta'
        verbose_name_plural = 'Pagos de cuota de venta'
        ordering = ['-fecha', '-id']

    def __str__(self):
        return f'Pago ${self.valor} - Cuota {self.cuota.numero} (Factura #{self.cuota.factura_id})'


class PayPalCuotaOrder(models.Model):
    """Vincula una orden de PayPal (single o multi-cuota) con la factura y
    las cuotas exactas para las que fue creada. Al capturar, se exige que
    el orderID recibido corresponda a un registro aquí y se usan las cuotas
    guardadas (no las que el cliente reenvíe en el body), para que una
    orden no pueda reutilizarse contra cuotas o facturas distintas."""

    order_id = models.CharField(max_length=32, unique=True, verbose_name='ID de orden (PayPal)')
    factura = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, related_name='paypal_cuota_orders',
        verbose_name='Factura',
    )
    cuota_ids = models.JSONField(verbose_name='IDs de cuotas incluidas')
    captured = models.BooleanField(default=False, verbose_name='Capturada')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Orden PayPal de cuota(s)'
        verbose_name_plural = 'Órdenes PayPal de cuotas'

    def __str__(self):
        return f'Orden PayPal {self.order_id} - Factura #{self.factura_id}'
