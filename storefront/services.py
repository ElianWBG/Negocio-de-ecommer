from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from billing.models import Product, Invoice, InvoiceDetail


class InsufficientStockError(Exception):
    """Se lanza cuando, al momento de confirmar, ya no hay stock suficiente
    de algún producto. La transacción completa se revierte."""
    pass


def confirm_purchase_request(purchase_request):
    """Convierte una PurchaseRequest pendiente en una Factura real.

    Usada tanto por la confirmación manual del proveedor (panel interno)
    como por la confirmación automática cuando un pago con tarjeta es
    aprobado (PayPhone). En ambos casos el stock se descuenta de forma
    atómica con una actualización condicional (stock__gte=cantidad), para
    evitar vender más de lo que realmente hay disponible si dos solicitudes
    piden el mismo producto casi al mismo tiempo.

    Lanza InsufficientStockError si algún producto ya no alcanza; en ese
    caso no se crea ninguna factura ni se descuenta nada (todo o nada).
    """
    with transaction.atomic():
        invoice = Invoice.objects.create(customer=purchase_request.customer)

        for detail in purchase_request.details.select_related('product'):
            updated = Product.objects.filter(
                pk=detail.product_id,
                stock__gte=detail.quantity
            ).update(stock=F('stock') - detail.quantity)
            if not updated:
                raise InsufficientStockError(
                    f'"{detail.product.name}" ya no tiene stock suficiente '
                    f'para confirmar {detail.quantity} unidades.'
                )
            InvoiceDetail.objects.create(
                invoice=invoice,
                product=detail.product,
                quantity=detail.quantity,
                unit_price=detail.unit_price,
            )

        subtotal = sum(d.subtotal for d in invoice.details.all())
        invoice.subtotal = subtotal
        invoice.tax = subtotal * Decimal('0.15')
        invoice.total = invoice.subtotal + invoice.tax
        invoice.save()

        purchase_request.status = 'confirmada'
        purchase_request.invoice = invoice
        purchase_request.reviewed_at = timezone.now()
        purchase_request.save()

    return invoice
