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

    _send_purchase_confirmation_email(purchase_request, invoice)
    return invoice


def _send_purchase_confirmation_email(purchase_request, invoice):
    """Envía un correo de confirmación al cliente cuando su compra se confirma.
    Si falla el envío, no interrumpe la confirmación (fail_silently)."""
    from django.core.mail import EmailMultiAlternatives
    from django.utils.html import strip_tags
    from billing.models import ConfigNegocio
    from billing.xml_utils import generate_invoice_xml, invoice_xml_filename

    customer = purchase_request.customer
    if not customer.email:
        return
    config = ConfigNegocio.objects.first()
    store_name = (config.nombre_tienda if config else None) or 'nuestra tienda'

    rows = ''.join(
        f'<tr><td style="padding:4px 8px;">{d.product.name}</td>'
        f'<td style="padding:4px 8px;text-align:center;">{d.quantity}</td>'
        f'<td style="padding:4px 8px;text-align:right;">${d.subtotal}</td></tr>'
        for d in invoice.details.all()
    )
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width:560px; margin:0 auto;">
      <h2 style="color:#B5441B;">¡Gracias por tu compra, {customer.first_name}!</h2>
      <p>Tu pedido #{purchase_request.id} fue confirmado. Aquí el resumen:</p>
      <table style="width:100%; border-collapse:collapse;">
        <thead>
          <tr style="background:#F1EEE9;">
            <th style="padding:4px 8px;text-align:left;">Producto</th>
            <th style="padding:4px 8px;">Cant.</th>
            <th style="padding:4px 8px;text-align:right;">Subtotal</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
      <p style="margin-top:1rem;"><strong>Total: ${invoice.total}</strong></p>
      <p style="margin-top:2rem; color:#888; font-size:.85rem;">Este es un correo automático de {store_name}.</p>
    </div>
    """
    try:
        message = EmailMultiAlternatives(
            subject=f'Pedido #{purchase_request.id} confirmado',
            body=strip_tags(html_content),
            from_email=None,
            to=[customer.email],
        )
        message.attach_alternative(html_content, 'text/html')

        # Adjunta la factura en XML (formato de práctica, no válido ante el SRI).
        try:
            xml_bytes = generate_invoice_xml(invoice)
            message.attach(invoice_xml_filename(invoice), xml_bytes, 'application/xml')
        except Exception:
            # Si falla la generación del XML no debe bloquear el envío del correo.
            pass

        message.send(fail_silently=True)
    except Exception:
        pass
