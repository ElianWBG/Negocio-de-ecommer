import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from billing.models import Product, Invoice, InvoiceDetail

logger = logging.getLogger(__name__)


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

    try:
        _send_purchase_confirmation_email(purchase_request, invoice)
    except Exception as e:
        logger.exception('Error al enviar correo de confirmación para pedido #%s: %s', purchase_request.pk, e)
    return invoice


def confirm_purchase_request_credito(purchase_request, numero_cuotas):
    """Convierte una PurchaseRequest pendiente en una Factura a CRÉDITO, con
    su cronograma de cuotas generado automáticamente.

    Mismo mecanismo "todo o nada" que confirm_purchase_request (descuento de
    stock atómico), más la verificación del límite de crédito del cliente:
    si no hay stock suficiente o el crédito no alcanza, no se crea ni la
    factura ni las cuotas, y no se descuenta nada.
    """
    from billing.services import check_credit_limit
    from creditos_ventas.services import generar_cuotas

    if numero_cuotas <= 0:
        raise ValueError('El número de cuotas debe ser mayor a cero.')

    with transaction.atomic():
        invoice = Invoice.objects.create(customer=purchase_request.customer, tipo_pago='credito')

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

        check_credit_limit(purchase_request.customer, invoice.total)

        invoice.saldo = invoice.total
        invoice.estado = 'pendiente'
        invoice.save()

        generar_cuotas(invoice, numero_cuotas)

        purchase_request.status = 'confirmada'
        purchase_request.invoice = invoice
        purchase_request.payment_method = 'credito'
        purchase_request.reviewed_at = timezone.now()
        purchase_request.save()

    try:
        _send_purchase_confirmation_email(purchase_request, invoice)
    except Exception as e:
        logger.exception('Error al enviar correo de confirmación para pedido #%s: %s', purchase_request.pk, e)
    return invoice


def _send_purchase_confirmation_email(purchase_request, invoice):
    """Envía un correo de confirmación al cliente cuando su compra se confirma.
    Si falla el envío, no interrumpe la confirmación (fail_silently)."""
    from django.core.mail import EmailMultiAlternatives
    from django.utils.html import strip_tags
    from billing.models import ConfigNegocio
    from billing.services import build_invoice_pdf
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
    # Logo de la tienda (ConfigNegocio.logo). En producción con Cloudinary,
    # .url es una URL absoluta https que los clientes de correo cargan bien.
    logo_html = ''
    if config and getattr(config, 'logo', None):
        try:
            logo_html = (
                f'<img src="{config.logo.url}" alt="{store_name}" '
                f'style="max-height:56px;max-width:220px;margin-bottom:14px;">'
            )
        except Exception:
            logo_html = ''
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width:560px; margin:0 auto;">
      {logo_html}
      <h2 style="color:#1D2B4A;">¡Gracias por tu compra, {customer.first_name}!</h2>
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

        # Adjunta la factura en PDF (formato RIDE, legible para el cliente).
        try:
            pdf_buffer = build_invoice_pdf(invoice)
            message.attach(f'factura_{invoice.pk:05d}.pdf', pdf_buffer.getvalue(), 'application/pdf')
        except Exception:
            logger.exception('No se pudo generar el PDF de la factura para el pedido %s', purchase_request.pk)

        # Adjunta también la factura en XML.
        try:
            xml_bytes = generate_invoice_xml(invoice)
            message.attach(invoice_xml_filename(invoice), xml_bytes, 'application/xml')
        except Exception:
            logger.exception('No se pudo generar el XML de la factura para el pedido %s', purchase_request.pk)

        message.send(fail_silently=False)
    except Exception:
        logger.exception('Error sending purchase confirmation email to %s', customer.email)
        pass
