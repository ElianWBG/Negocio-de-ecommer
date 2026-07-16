from django.db import models

from purchasing.models import Purchase


class CuotaCompra(models.Model):
    """Una cuota del cronograma de pagos de una compra a crédito."""

    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('pagada', 'Pagada'),
    ]

    compra = models.ForeignKey(
        Purchase, on_delete=models.PROTECT, related_name='cuotas',
        verbose_name='Compra',
    )
    numero = models.PositiveIntegerField(verbose_name='N° de cuota')
    fecha_vencimiento = models.DateField(verbose_name='Fecha de vencimiento')
    valor = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Valor de la cuota')
    saldo = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Saldo pendiente')
    estado = models.CharField(
        max_length=15, choices=ESTADO_CHOICES, default='pendiente',
        verbose_name='Estado',
    )

    class Meta:
        verbose_name = 'Cuota de compra'
        verbose_name_plural = 'Cuotas de compra'
        ordering = ['compra', 'numero']
        constraints = [
            models.UniqueConstraint(
                fields=['compra', 'numero'], name='unique_compra_numero_cuota',
            )
        ]

    def __str__(self):
        return f'Cuota {self.numero} - Compra #{self.compra_id}'


class PagoCuotaCompra(models.Model):
    """Registro de un abono realizado sobre una cuota de una compra a crédito.
    Una cuota puede recibir múltiples pagos parciales hasta cancelarse."""

    cuota = models.ForeignKey(
        CuotaCompra, on_delete=models.PROTECT, related_name='pagos',
        verbose_name='Cuota',
    )
    fecha = models.DateField(verbose_name='Fecha de pago')
    valor = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Valor abonado')
    observacion = models.TextField(blank=True, verbose_name='Observación')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Pago de cuota de compra'
        verbose_name_plural = 'Pagos de cuota de compra'
        ordering = ['-fecha', '-id']

    def __str__(self):
        return f'Pago ${self.valor} - Cuota {self.cuota.numero} (Compra #{self.cuota.compra_id})'
