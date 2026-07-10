from django.db import models


class PurchaseRequest(models.Model):
    STATUS_CHOICES = [
        ('pendiente',  'Pendiente'),
        ('confirmada', 'Confirmada'),
        ('rechazada',  'Rechazada'),
        ('cancelada',  'Cancelada por el cliente'),
    ]
    PAYMENT_METHOD_CHOICES = [
        ('manual', 'Revisión manual del proveedor'),
        ('tarjeta', 'Tarjeta de crédito/débito (PayPhone)'),
    ]

    customer = models.ForeignKey(
        'billing.Customer', on_delete=models.PROTECT,
        related_name='purchase_requests', verbose_name='Cliente'
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pendiente', verbose_name='Estado')
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES, default='manual', verbose_name='Método de pago')
    notes = models.TextField(blank=True, null=True, verbose_name='Notas')
    invoice = models.ForeignKey(
        'billing.Invoice', on_delete=models.SET_NULL, blank=True, null=True,
        related_name='source_request', verbose_name='Factura generada'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de solicitud')
    reviewed_at = models.DateTimeField(blank=True, null=True, verbose_name='Fecha de revisión')
    payphone_client_transaction_id = models.CharField(max_length=20, unique=True, blank=True, null=True, verbose_name='ID de transacción (nuestro)')
    payphone_transaction_id = models.IntegerField(blank=True, null=True, verbose_name='ID de transacción (PayPhone)')

    class Meta:
        verbose_name = 'Solicitud de compra'
        verbose_name_plural = 'Solicitudes de compra'
        ordering = ['-created_at']

    def __str__(self):
        return f'Solicitud #{self.id} - {self.customer} ({self.get_status_display()})'

    def can_be_cancelled(self):
        return self.status == 'pendiente'

    @property
    def subtotal_estimado(self):
        return sum(d.subtotal for d in self.details.all())

    @property
    def tax_estimado(self):
        from decimal import Decimal
        return round(self.subtotal_estimado * Decimal('0.15'), 2)

    @property
    def total_estimado(self):
        return self.subtotal_estimado + self.tax_estimado


class PurchaseRequestDetail(models.Model):
    """Línea de producto dentro de una solicitud de compra."""
    request = models.ForeignKey(PurchaseRequest, on_delete=models.CASCADE, related_name='details', verbose_name='Solicitud')
    product = models.ForeignKey('billing.Product', on_delete=models.PROTECT, related_name='purchase_request_details', verbose_name='Producto')
    quantity = models.PositiveIntegerField(default=1, verbose_name='Cantidad')
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Precio unitario')

    class Meta:
        verbose_name = 'Detalle de solicitud'
        verbose_name_plural = 'Detalles de solicitud'

    def __str__(self):
        return f'{self.product.name} x {self.quantity}'

    @property
    def subtotal(self):
        return round(self.unit_price * self.quantity, 2)


class EmailVerificationToken(models.Model):
    """Token de un solo uso para verificar el email al registrarse.
    Expira a las 24 horas de crearse."""
    user = models.OneToOneField(
        'auth.User', on_delete=models.CASCADE,
        related_name='email_verification_token'
    )
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Token de verificación de email'

    def __str__(self):
        return f'Token de {self.user.email}'

    @property
    def is_expired(self):
        from django.utils import timezone
        from datetime import timedelta
        return timezone.now() > self.created_at + timedelta(hours=24)
