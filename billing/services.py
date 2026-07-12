import secrets
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .models import PanelVerificationCode


def _clave_acceso_demo(invoice, config):
    """Genera una clave de acceso de 49 dígitos (formato SRI) con dígito
    verificador Módulo 11. DEMO: no corresponde a una autorización real."""
    fecha = invoice.invoice_date.strftime('%d%m%Y')
    ruc = ''.join(ch for ch in (getattr(config, 'ruc', '') or '') if ch.isdigit()).ljust(13, '0')[:13]
    secuencial = f'{invoice.id:09d}'
    cuerpo = (
        f'{fecha}01{ruc}2001001{secuencial}12345678' '1'
    )  # fecha(8)+tipo(2)+ruc(13)+amb(1)+serie(6)+sec(9)+cod(8)+tipoEmision(1) = 48
    cuerpo = cuerpo[:48].ljust(48, '0')
    pesos = [2, 3, 4, 5, 6, 7]
    total = sum(int(d) * pesos[i % 6] for i, d in enumerate(reversed(cuerpo)))
    dv = 11 - (total % 11)
    dv = 0 if dv == 11 else (1 if dv == 10 else dv)
    return f'{cuerpo}{dv}'


def build_invoice_pdf(invoice):
    """Build a ReportLab PDF (formato tipo RIDE del SRI). Returns a BytesIO buffer.

    Shared by billing.views.invoice_pdf (staff) and
    storefront.views.customer_invoice_pdf (owner check).
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm, mm
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    )
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
    from reportlab.graphics.barcode import code128
    import io
    from decimal import Decimal
    from django.utils import timezone

    from billing.models import ConfigNegocio
    config = ConfigNegocio.get()

    black = colors.HexColor('#111111')
    line = colors.HexColor('#333333')
    grey = colors.HexColor('#555555')

    USABLE_W = A4[0] - 3 * cm

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm, topMargin=1.2*cm, bottomMargin=1.2*cm,
    )

    def ps(name, **kw):
        base = dict(fontName='Helvetica', fontSize=8, textColor=black, leading=11)
        base.update(kw)
        return ParagraphStyle(name, **base)

    s_lbl = ps('lbl', fontName='Helvetica', fontSize=7.5, textColor=grey)
    s_val = ps('val', fontName='Helvetica-Bold', fontSize=8.5)
    s_sm = ps('sm', fontSize=7.5)
    s_smb = ps('smb', fontName='Helvetica-Bold', fontSize=8)
    s_big = ps('big', fontName='Helvetica-Bold', fontSize=13)
    s_center = ps('c', alignment=TA_CENTER, fontSize=7)

    clave = _clave_acceso_demo(invoice, config)
    numero = f'001-001-{invoice.id:09d}'

    # ── EMISOR (izq) ──────────────────────────────────────────────
    emisor_cell = []
    if getattr(config, 'logo', None):
        try:
            from reportlab.platypus import Image as RLImage
            emisor_cell.append(RLImage(config.logo.path, width=4.5*cm, height=1.4*cm, kind='proportional'))
            emisor_cell.append(Spacer(1, 4))
        except Exception:
            emisor_cell.append(Paragraph(config.nombre_tienda, s_big))
    else:
        emisor_cell.append(Paragraph(config.nombre_tienda, s_big))
    emisor_cell.append(Spacer(1, 6))
    emisor_cell.append(Paragraph(f'<b>{config.nombre_tienda}</b>', s_smb))
    if config.direccion:
        emisor_cell.append(Paragraph(f'Matriz: {config.direccion}', s_sm))
        emisor_cell.append(Paragraph(f'Sucursal: {config.direccion}', s_sm))
    emisor_cell.append(Paragraph(
        f'OBLIGADO A LLEVAR CONTABILIDAD: {getattr(config, "obligado_contabilidad", "NO") or "NO"}', s_sm))

    # ── Recuadro comprobante (der) ────────────────────────────────
    bc = code128.Code128(clave, barHeight=11*mm, barWidth=0.32*mm)
    comp_rows = [
        [Paragraph(f'RUC: {getattr(config, "ruc", "") or "N/A"}', s_smb)],
        [Paragraph('<b>FACTURA</b>', ps('f', fontSize=10))],
        [Paragraph(f'No.: {numero}', s_smb)],
        [Paragraph('NÚMERO DE AUTORIZACIÓN', s_lbl)],
        [Paragraph(clave, s_sm)],
        [Paragraph('FECHA Y HORA DE AUTORIZACIÓN', s_lbl)],
        [Paragraph(invoice.invoice_date.strftime('%d/%m/%Y %H:%M:%S'), s_sm)],
        [Paragraph('AMBIENTE: PRUEBAS &nbsp;&nbsp; EMISIÓN: NORMAL', s_sm)],
        [Paragraph('CLAVE DE ACCESO', s_lbl)],
        [bc],
        [Paragraph(clave, s_center)],
    ]
    comp = Table(comp_rows, colWidths=[USABLE_W * 0.46 - 6])
    comp.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('BOX', (0, 0), (-1, -1), 0.7, line),
        ('ALIGN', (0, 9), (0, 10), 'CENTER'),
    ]))

    top = Table([[emisor_cell, comp]], colWidths=[USABLE_W * 0.54, USABLE_W * 0.46])
    top.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOX', (0, 0), (0, 0), 0.7, line),
        ('LEFTPADDING', (0, 0), (0, 0), 8), ('RIGHTPADDING', (0, 0), (0, 0), 8),
        ('TOPPADDING', (0, 0), (0, 0), 8), ('BOTTOMPADDING', (0, 0), (0, 0), 8),
        ('LEFTPADDING', (1, 0), (1, 0), 4),
    ]))
    elements = [top, Spacer(1, 6)]

    # ── Banda comprador ───────────────────────────────────────────
    cust = invoice.customer
    comprador = Table([
        [Paragraph(f'<b>Razón Social / Nombres y Apellidos:</b> {cust.full_name}', s_sm)],
        [Paragraph(f'<b>RUC / C.I.:</b> {cust.dni} &nbsp;&nbsp;&nbsp; '
                   f'<b>Fecha Emisión:</b> {invoice.invoice_date.strftime("%d/%m/%Y")} &nbsp;&nbsp;&nbsp; '
                   f'<b>Guía Remisión:</b> --', s_sm)],
        [Paragraph(f'<b>Dirección:</b> {cust.address or "--"}', s_sm)],
    ], colWidths=[USABLE_W])
    comprador.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.7, line),
        ('LEFTPADDING', (0, 0), (-1, -1), 8), ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements += [comprador, Spacer(1, 6)]

    # ── Detalle de productos ──────────────────────────────────────
    details = invoice.details.select_related('product', 'product__brand').all()
    head = ['Cod.\nPrincipal', 'Cod.\nAuxiliar', 'Cant.', 'Descripción', 'Precio\nUnitario', 'Desc.', 'Precio Total']
    rows = [[Paragraph(f'<b>{h}</b>', s_center) for h in head]]
    for d in details:
        rows.append([
            Paragraph(str(d.product_id), s_sm),
            Paragraph('--', s_sm),
            Paragraph(str(d.quantity), s_center),
            Paragraph(d.product.name, s_sm),
            Paragraph(f'{d.unit_price}', ps('r', alignment=TA_RIGHT, fontSize=8)),
            Paragraph('0.00', ps('r2', alignment=TA_RIGHT, fontSize=8)),
            Paragraph(f'{d.subtotal}', ps('r3', alignment=TA_RIGHT, fontSize=8)),
        ])
    prod = Table(rows, colWidths=[2.0*cm, 1.6*cm, 1.2*cm, USABLE_W - 11.1*cm, 2.1*cm, 1.4*cm, 2.8*cm], repeatRows=1)
    prod.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, line),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements += [prod, Spacer(1, 6)]

    # ── Forma de pago (izq) + Totales (der) ───────────────────────
    forma = Table([
        [Paragraph('<b>Forma de pago</b>', s_center), Paragraph('<b>Total</b>', s_center),
         Paragraph('<b>Plazo</b>', s_center), Paragraph('<b>Unidad de\ntiempo</b>', s_center)],
        [Paragraph('OTROS CON UTILIZACIÓN DEL SISTEMA FINANCIERO', s_sm),
         Paragraph(f'{invoice.total}', s_center), Paragraph('0', s_center), Paragraph('Días', s_center)],
    ], colWidths=[3.4*cm, 1.8*cm, 1.3*cm, 1.9*cm])
    forma.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, line),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))

    money = lambda v: f'{Decimal(v):.2f}'
    tot_rows = [
        ['SUBTOTAL SIN IMPUESTOS', money(invoice.subtotal)],
        ['SUBTOTAL 0%', '0.00'],
        ['SUBTOTAL 15%', money(invoice.subtotal)],
        ['SUBTOTAL No sujeto IVA', '0.00'],
        ['SUBTOTAL Exento de IVA', '0.00'],
        ['TOTAL DESCUENTO', '0.00'],
        ['ICE', '0.00'],
        ['IVA 15%', money(invoice.tax)],
        ['PROPINA / SERVICIO', '0.00'],
        ['VALOR TOTAL', money(invoice.total)],
    ]
    tot = Table([[Paragraph(f'<b>{k}</b>', ps('k', fontSize=7.5)),
                  Paragraph(v, ps('v', alignment=TA_RIGHT, fontSize=8))] for k, v in tot_rows],
                colWidths=[4.6*cm, 2.6*cm])
    tot.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, line),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#EFEFEF')),
        ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 5), ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    bottom = Table([[forma, tot]], colWidths=[USABLE_W - 7.5*cm, 7.5*cm])
    bottom.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    elements += [bottom, Spacer(1, 8)]

    # ── Información adicional ──────────────────────────────────────
    info_rows = [[Paragraph('<b>Información Adicional</b>', s_center)]]
    adic = [
        ('Emisor', config.nombre_tienda),
        ('RUC', getattr(config, 'ruc', '') or 'N/A'),
        ('Matriz', config.direccion or '--'),
        ('Obligado a llevar contabilidad', getattr(config, 'obligado_contabilidad', 'NO') or 'NO'),
        ('Email cliente', cust.email or '--'),
        ('Número de pedido cliente', f'{invoice.id:08d}'),
    ]
    info = Table(
        [[Paragraph('<b>Información Adicional</b>', s_center), '']] +
        [[Paragraph(k, s_sm), Paragraph(str(v), s_sm)] for k, v in adic],
        colWidths=[5*cm, USABLE_W - 5*cm],
    )
    info.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)),
        ('BOX', (0, 0), (-1, -1), 0.7, line),
        ('LINEBELOW', (0, 0), (-1, 0), 0.5, line),
        ('INNERGRID', (0, 1), (-1, -1), 0.3, colors.HexColor('#CCCCCC')),
        ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements += [info, Spacer(1, 10)]

    elements.append(Paragraph(
        'Documento con formato RIDE. NO es un comprobante fiscal electrónico '
        'autorizado por el SRI y no tiene validez tributaria.',
        ps('foot', fontSize=6.5, textColor=grey, alignment=TA_CENTER)))

    doc.build(elements)
    return buffer


def register_invoice_payment(invoice, amount, method, user, notes=''):
    """Registra un pago (total o parcial) contra una factura de crédito.

    Actualiza saldo y estado de la factura de forma atómica.
    Retorna el InvoicePayment creado.
    """
    from billing.models import InvoicePayment

    amount = Decimal(str(amount))
    if amount <= 0:
        raise ValueError('El monto debe ser mayor a cero.')
    if amount > invoice.saldo:
        raise ValueError(
            f'El monto (${amount:.2f}) supera el saldo pendiente (${invoice.saldo:.2f}).'
        )

    with transaction.atomic():
        inv = invoice.__class__.objects.select_for_update().get(pk=invoice.pk)

        if amount > inv.saldo:
            raise ValueError(
                f'El monto (${amount:.2f}) supera el saldo pendiente (${inv.saldo:.2f}).'
            )

        payment = InvoicePayment.objects.create(
            invoice=inv,
            amount=amount,
            method=method,
            registered_by=user,
            notes=notes,
        )

        inv.saldo = max(Decimal('0'), inv.saldo - amount)
        inv.estado = 'pagada' if inv.saldo == 0 else 'parcial'
        inv.save(update_fields=['saldo', 'estado'])

    invoice.saldo = inv.saldo
    invoice.estado = inv.estado
    return payment


def check_credit_limit(customer, new_invoice_total):
    """Lanza ValueError si el nuevo crédito supera el límite del cliente."""
    from billing.models import Invoice

    try:
        limit = customer.profile.credit_limit
    except Exception:
        return

    if limit <= 0:
        return

    pending_debt = (
        Invoice.objects
        .filter(customer=customer, tipo_pago='credito', is_active=True)
        .exclude(estado='pagada')
        .aggregate(s=Sum('saldo'))['s']
    ) or Decimal('0')

    total = Decimal(str(new_invoice_total))
    if pending_debt + total > limit:
        raise ValueError(
            f'Este cliente tiene ${pending_debt:.2f} de deuda pendiente y un límite de '
            f'crédito de ${limit:.2f}. La factura de ${total:.2f} excedería ese límite.'
        )


def _generate_verification_code():
    return f'{secrets.randbelow(1000000):06d}'


def _send_panel_verification_code(user, request=None):
    if not user.email:
        return None
    code_obj, created = PanelVerificationCode.objects.update_or_create(
        user=user,
        defaults={'code': _generate_verification_code(), 'is_used': False},
    )
    from django.urls import reverse
    if request:
        verify_url = request.build_absolute_uri(reverse('billing:verify_panel_code'))
    else:
        verify_url = f'{settings.SITE_URL}{reverse("billing:verify_panel_code")}'
    subject = 'Tu código de verificación — Panel de Administración'
    html_content = render_to_string('billing/emails/verification_code.html', {
        'user': user,
        'code': code_obj.code,
        'verify_url': verify_url,
    })
    msg = EmailMultiAlternatives(
        subject=subject,
        body=strip_tags(html_content),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    msg.attach_alternative(html_content, 'text/html')
    try:
        msg.send(fail_silently=False)
    except Exception:
        pass
    return code_obj
