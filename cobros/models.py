from django.db import models
from billing.models import Invoice


class CobroFactura(models.Model):
    """Registro de un abono / pago realizado por un cliente sobre una
    factura de venta a crédito. Una factura puede tener muchos cobros."""

    factura = models.ForeignKey(
        Invoice, on_delete=models.PROTECT, related_name='cobros',
        verbose_name='Factura',
    )
    fecha = models.DateField(verbose_name='Fecha de pago')
    valor = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name='Valor abonado',
    )
    observacion = models.TextField(blank=True, verbose_name='Observación')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Cobro de factura'
        verbose_name_plural = 'Cobros de factura'
        ordering = ['-fecha', '-id']

    def __str__(self):
        return f'Cobro ${self.valor} - Factura #{self.factura_id}'
