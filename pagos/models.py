from django.db import models
from purchasing.models import Purchase


class PagoCompra(models.Model):
    """Registro de un abono realizado a un proveedor sobre una compra a
    crédito. Una compra puede tener muchos pagos."""

    compra = models.ForeignKey(
        Purchase, on_delete=models.PROTECT, related_name='pagos',
        verbose_name='Compra',
    )
    fecha = models.DateField(verbose_name='Fecha de pago')
    valor = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name='Valor abonado',
    )
    observacion = models.TextField(blank=True, verbose_name='Observación')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Pago de compra'
        verbose_name_plural = 'Pagos de compra'
        ordering = ['-fecha', '-id']

    def __str__(self):
        return f'Pago ${self.valor} - Compra #{self.compra_id}'
