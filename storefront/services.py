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

    try:
        from shared.sri_client import emitir_factura_sri
        emitir_factura_sri(invoice)
    except Exception:
        logger.exception('Error enviando factura #%s al micro SRI', invoice.pk)

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

    try:
        from shared.sri_client import emitir_factura_sri
        emitir_factura_sri(invoice)
    except Exception:
        logger.exception('Error enviando factura #%s al micro SRI', invoice.pk)

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

    from django.utils import timezone as tz
    date_str = invoice.invoice_date.strftime('%d/%m/%Y') if invoice.invoice_date else tz.localdate().strftime('%d/%m/%Y')

    tipo_pago_label = {
        'contado': 'EFECTIVO / TRANSFERENCIA',
        'credito': 'CRÉDITO (CUOTAS)',
        'paypal': 'PAYPAL',
    }.get(invoice.tipo_pago, (invoice.tipo_pago or '').upper())

    customer_name = f'{customer.first_name} {customer.last_name}'.strip().upper()

    rows = ''.join(
        f'<tr style="border-bottom:1px solid #F1EEE9;">'
        f'<td style="padding:9px 12px;color:#231A10;">{d.product.name}</td>'
        f'<td style="padding:9px 12px;text-align:center;color:#231A10;">{d.quantity}</td>'
        f'<td style="padding:9px 12px;text-align:right;color:#231A10;">${d.subtotal:.2f}</td>'
        f'</tr>'
        for d in invoice.details.all()
    )

    logo_html = ''
    if config and getattr(config, 'logo', None):
        try:
            logo_html = (
                f'<img src="{config.logo.url}" alt="{store_name}" '
                f'style="max-height:52px;max-width:200px;display:block;margin:0 auto 10px;">'
            )
        except Exception:
            logo_html = ''

    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:20px 0;background:#F8F4F0;font-family:Arial,Helvetica,sans-serif;">
<div style="max-width:600px;margin:0 auto;background:#ffffff;border:1px solid #DDD5CC;border-radius:4px;overflow:hidden;">

  <!-- HEADER -->
  <div style="background:#B5441B;padding:28px 32px;text-align:center;">
    {logo_html}
    <h1 style="color:#ffffff;font-size:22px;margin:0;letter-spacing:2px;text-transform:uppercase;">{store_name}</h1>
    <p style="color:rgba(255,255,255,0.8);font-size:11px;margin:5px 0 0;letter-spacing:2px;text-transform:uppercase;">FACTURA ELECTRÓNICA</p>
  </div>

  <!-- DATE BAND -->
  <div style="background:#231A10;padding:9px 32px;text-align:center;">
    <p style="color:#F8F4F0;font-size:11px;letter-spacing:2px;margin:0;text-transform:uppercase;">PERIODO {date_str}</p>
  </div>

  <!-- CUSTOMER -->
  <div style="padding:24px 32px 20px;border-bottom:1px solid #EDE7E0;">
    <h2 style="font-size:19px;color:#231A10;margin:0 0 4px;text-transform:uppercase;letter-spacing:1px;">{customer_name}</h2>
    <p style="color:#7A6358;font-size:13px;margin:2px 0;">Cédula / RUC: {customer.dni}</p>
    <p style="color:#7A6358;font-size:13px;margin:2px 0;">{customer.email}</p>
  </div>

  <!-- INVOICE DETAILS BOX -->
  <div style="margin:20px 32px;border:1px solid #DDD5CC;border-radius:4px;overflow:hidden;font-size:13px;">
    <table style="width:100%;border-collapse:collapse;">
      <tr style="border-bottom:1px solid #EDE7E0;">
        <td style="padding:10px 16px;color:#7A6358;width:48%;">No. de Factura</td>
        <td style="padding:10px 16px;color:#231A10;font-weight:bold;">#{invoice.pk:05d}</td>
      </tr>
      <tr style="border-bottom:1px solid #EDE7E0;">
        <td style="padding:10px 16px;color:#7A6358;">Pedido</td>
        <td style="padding:10px 16px;color:#231A10;font-weight:bold;">#{purchase_request.id}</td>
      </tr>
      <tr style="border-bottom:1px solid #EDE7E0;">
        <td style="padding:10px 16px;color:#7A6358;">Fecha de emisión</td>
        <td style="padding:10px 16px;color:#231A10;">{date_str}</td>
      </tr>
      <tr>
        <td style="padding:10px 16px;color:#7A6358;">Forma de pago</td>
        <td style="padding:10px 16px;color:#231A10;">{tipo_pago_label}</td>
      </tr>
    </table>
  </div>

  <!-- PRODUCTS TABLE -->
  <div style="margin:0 32px 8px;">
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
      <thead>
        <tr style="background:#F1EEE9;">
          <th style="padding:9px 12px;text-align:left;color:#7A6358;font-size:10px;letter-spacing:1px;text-transform:uppercase;font-weight:700;">Producto</th>
          <th style="padding:9px 12px;text-align:center;color:#7A6358;font-size:10px;letter-spacing:1px;text-transform:uppercase;font-weight:700;">Cant.</th>
          <th style="padding:9px 12px;text-align:right;color:#7A6358;font-size:10px;letter-spacing:1px;text-transform:uppercase;font-weight:700;">Subtotal</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>

    <!-- TOTALS -->
    <table style="width:100%;border-collapse:collapse;font-size:13px;margin-top:2px;">
      <tr>
        <td style="padding:6px 12px;text-align:right;color:#7A6358;">Subtotal sin IVA</td>
        <td style="padding:6px 12px;text-align:right;color:#231A10;width:110px;">${invoice.subtotal:.2f}</td>
      </tr>
      <tr>
        <td style="padding:6px 12px;text-align:right;color:#7A6358;">IVA</td>
        <td style="padding:6px 12px;text-align:right;color:#231A10;">${invoice.tax:.2f}</td>
      </tr>
      <tr style="border-top:2px solid #B5441B;">
        <td style="padding:12px 12px;text-align:right;font-weight:bold;font-size:17px;color:#B5441B;">TOTAL</td>
        <td style="padding:12px 12px;text-align:right;font-weight:bold;font-size:17px;color:#B5441B;">${invoice.total:.2f}</td>
      </tr>
    </table>
  </div>

  <!-- FOOTER -->
  <div style="background:#231A10;padding:20px 32px;text-align:center;margin-top:12px;">
    <p style="color:#F8F4F0;font-size:12px;margin:0 0 4px;">Gracias por confiar en <strong>{store_name}</strong>.</p>
    <p style="color:rgba(255,255,255,0.5);font-size:11px;margin:0;">Los archivos adjuntos incluyen tu factura en PDF y XML.</p>
  </div>

</div>
</body>
</html>"""
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
