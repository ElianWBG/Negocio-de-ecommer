from django.db import models
from decimal import Decimal
from billing.models import Supplier, Product   # Reutilizamos modelos de billing


class Purchase(models.Model):
    """Cabecera de compra. Documenta una adquisición a un proveedor."""
    supplier = models.ForeignKey(
        Supplier, on_delete=models.PROTECT, related_name='purchases'
    )
    document_number = models.CharField(
        max_length=20, verbose_name='Supplier Invoice No.'
    )
    purchase_date = models.DateTimeField(auto_now_add=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    estado = models.CharField(
        max_length=10,
        choices=[('pendiente', 'Pendiente'), ('parcial', 'Parcial'), ('pagada', 'Pagada'), ('anulada', 'Anulada')],
        default='pendiente',
        verbose_name='Estado de pago',
    )
    saldo = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Saldo pendiente')
    tipo_pago = models.CharField(
        max_length=10,
        choices=[('contado', 'Contado'), ('credito', 'Crédito')],
        default='contado',
        verbose_name='Tipo de pago',
    )

    class Meta:
        verbose_name = 'Compra a proveedor'
        verbose_name_plural = 'Compras a proveedores'
        ordering = ['-purchase_date']
        # Reto opcional: no permitir el mismo número de documento dos veces
        # para un mismo proveedor.
        constraints = [
            models.UniqueConstraint(
                fields=['supplier', 'document_number'],
                name='unique_supplier_document_number',
            )
        ]

    def __str__(self):
        return f'Purchase #{self.id} - {self.supplier}'

    def save(self, *args, **kwargs):
        if self.tipo_pago == 'contado' and self.estado != 'anulada':
            self.saldo = Decimal('0')
            self.estado = 'pagada'
        super().save(*args, **kwargs)


class PurchaseDetail(models.Model):
    """Líneas de compra. Cada fila es un producto adquirido."""
    purchase = models.ForeignKey(
        Purchase, on_delete=models.CASCADE, related_name='details'
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name='purchase_details'
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return f'{self.product.name} x {self.quantity}'

    def save(self, *args, **kwargs):
        self.subtotal = self.quantity * self.unit_cost
        super().save(*args, **kwargs)
