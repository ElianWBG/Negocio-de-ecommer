from decimal import Decimal
from django.db import transaction
from django.db.models import Sum


def build_invoice_pdf(invoice):
    """Build a ReportLab PDF for a single invoice. Returns a BytesIO buffer.

    Shared by billing.views.invoice_pdf (staff) and
    storefront.views.customer_invoice_pdf (owner check).
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle,
        Paragraph, Spacer, HRFlowable,
    )
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_RIGHT, TA_CENTER
    import io
    from django.utils import timezone

    from billing.models import ConfigNegocio
    config = ConfigNegocio.get()

    espresso = colors.HexColor('#231A10')
    rust     = colors.HexColor('#B5441B')
    sand     = colors.HexColor('#F8F3EE')
    grey     = colors.HexColor('#555555')

    USABLE_W = A4[0] - 3 * cm  # portrait A4 minus 1.5cm margins each side

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
    )

    def ps(name, **kw):
        return ParagraphStyle(name, **kw)

    s_store  = ps('Store', fontName='Helvetica-Bold', fontSize=13, textColor=espresso, spaceAfter=2)
    s_slogan = ps('Slogan', fontName='Helvetica', fontSize=8, textColor=colors.grey, spaceAfter=3)
    s_cinfo  = ps('CInfo', fontName='Helvetica', fontSize=8, textColor=grey)
    s_itag   = ps('ITag',  fontName='Helvetica-Bold', fontSize=7, textColor=rust, alignment=TA_RIGHT, spaceAfter=2)
    s_inum   = ps('INum',  fontName='Helvetica-Bold', fontSize=22, textColor=espresso,
                  alignment=TA_RIGHT, leading=26, spaceAfter=3)
    s_idate  = ps('IDate', fontName='Helvetica', fontSize=9, textColor=colors.grey,
                  alignment=TA_RIGHT, spaceAfter=4)
    s_sec    = ps('Sec',   fontName='Helvetica-Bold', fontSize=7, textColor=rust, spaceAfter=4)
    s_cname  = ps('CName', fontName='Helvetica-Bold', fontSize=11, textColor=espresso, spaceAfter=2)
    s_cdet   = ps('CDet',  fontName='Helvetica', fontSize=9, textColor=grey)
    s_foot   = ps('Foot',  fontName='Helvetica', fontSize=7, textColor=colors.grey, alignment=TA_CENTER)

    elements = []

    # ── Header ───────────────────────────────────────────────────
    left_col = [Paragraph(config.nombre_tienda, s_store)]
    if config.slogan:
        left_col.append(Paragraph(config.slogan, s_slogan))
    contacts = []
    if config.email_contacto:
        contacts.append(config.email_contacto)
    if config.telefono:
        contacts.append(config.telefono)
    if contacts:
        left_col.append(Paragraph('  '.join(contacts), s_cinfo))
    if config.direccion:
        left_col.append(Paragraph(config.direccion, s_cinfo))

    right_col = [
        Paragraph('FACTURA', s_itag),
        Paragraph(f'#{invoice.id:05d}', s_inum),
        Paragraph(invoice.invoice_date.strftime('%d/%m/%Y %H:%M'), s_idate),
    ]

    if invoice.estado == 'pagada':
        est_color, est_text = colors.HexColor('#065F46'), 'Pagada'
    elif invoice.estado == 'parcial':
        est_color = colors.HexColor('#92400E')
        est_text  = f'Pago parcial - Saldo ${invoice.saldo}'
    else:
        est_color = colors.HexColor('#991B1B')
        est_text  = f'Pendiente - Saldo ${invoice.saldo}'
    right_col.append(Paragraph(est_text, ps('Est', fontName='Helvetica-Bold', fontSize=8,
                                            textColor=est_color, alignment=TA_RIGHT, spaceAfter=2)))
    if invoice.tipo_pago == 'credito':
        right_col.append(Paragraph('Credito', ps('Cred', fontName='Helvetica', fontSize=8,
                                                  textColor=colors.HexColor('#1E40AF'), alignment=TA_RIGHT)))

    hdr = Table([[left_col, right_col]], colWidths=[USABLE_W * 0.55, USABLE_W * 0.45])
    hdr.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',   (0, 0), (-1, -1), 0),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
        ('TOPPADDING',    (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(hdr)
    elements.append(HRFlowable(width='100%', thickness=3, color=rust, spaceBefore=2, spaceAfter=10))

    # ── Facturado a ──────────────────────────────────────────────
    elements.append(Paragraph('FACTURADO A', s_sec))
    elements.append(Paragraph(invoice.customer.full_name, s_cname))
    if invoice.customer.email:
        elements.append(Paragraph(invoice.customer.email, s_cdet))
    if invoice.customer.phone:
        elements.append(Paragraph(invoice.customer.phone, s_cdet))
    elements.append(Paragraph(f'CI / RUC: {invoice.customer.dni}', s_cdet))
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width='100%', thickness=1, color=colors.HexColor('#F0F0F0'), spaceAfter=8))

    # ── Product table ─────────────────────────────────────────────
    elements.append(Paragraph('DETALLE DE PRODUCTOS', s_sec))
    details = invoice.details.select_related('product', 'product__brand').all()
    rows = [['#', 'Producto', 'Marca', 'Cant.', 'P. Unit.', 'Subtotal']]
    for i, d in enumerate(details, 1):
        rows.append([
            str(i),
            d.product.name,
            d.product.brand.name,
            str(d.quantity),
            f'${d.unit_price}',
            f'${d.subtotal}',
        ])

    prod = Table(rows, colWidths=[0.7*cm, 6.5*cm, 4.0*cm, 1.7*cm, 2.5*cm, 2.6*cm], repeatRows=1)
    prod.setStyle(TableStyle([
        ('BACKGROUND',     (0, 0), (-1, 0),  espresso),
        ('TEXTCOLOR',      (0, 0), (-1, 0),  colors.white),
        ('FONTNAME',       (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('FONTNAME',       (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE',       (0, 0), (-1, -1), 9),
        ('ALIGN',          (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN',          (1, 0), (2, -1),  'LEFT'),
        ('ALIGN',          (4, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME',       (-1, 1), (-1, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR',      (-1, 1), (-1, -1), rust),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [sand, colors.white]),
        ('GRID',           (0, 0), (-1, -1), 0.3, colors.HexColor('#DDD3C5')),
        ('TOPPADDING',     (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING',  (0, 0), (-1, -1), 5),
        ('LEFTPADDING',    (1, 0), (2, -1),  4),
    ]))
    elements.append(prod)
    elements.append(Spacer(1, 10))

    # ── Totals (right-aligned) ────────────────────────────────────
    tot = Table(
        [
            ['Subtotal',  f'${invoice.subtotal}'],
            ['IVA (15%)', f'${invoice.tax}'],
            ['', ''],
            ['TOTAL',     f'${invoice.total}'],
        ],
        colWidths=[4*cm, 3*cm],
    )
    tot.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), sand),
        ('FONTNAME',      (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE',      (0, 0), (-1, -1), 9),
        ('ALIGN',         (0, 0), (-1, -1), 'RIGHT'),
        ('TEXTCOLOR',     (0, 0), (0, 2),   grey),
        ('TEXTCOLOR',     (1, 0), (1, 2),   espresso),
        ('FONTNAME',      (0, 3), (-1, 3),  'Helvetica-Bold'),
        ('FONTSIZE',      (0, 3), (-1, 3),  12),
        ('TEXTCOLOR',     (0, 3), (-1, 3),  rust),
        ('LINEABOVE',     (0, 3), (-1, 3),  0.5, colors.HexColor('#E5E7EB')),
        ('TOPPADDING',    (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING',   (0, 0), (-1, -1), 8),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
        ('TOPPADDING',    (0, 2), (-1, 2),  1),
        ('BOTTOMPADDING', (0, 2), (-1, 2),  1),
    ]))
    spacer_w = USABLE_W - 7 * cm
    wrap = Table([['', tot]], colWidths=[spacer_w, 7*cm])
    wrap.setStyle(TableStyle([
        ('LEFTPADDING',   (0, 0), (-1, -1), 0),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
        ('TOPPADDING',    (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(wrap)

    # ── Payment history (if any) ──────────────────────────────────
    payments = list(invoice.payments.select_related('registered_by').all())
    if payments:
        elements.append(Spacer(1, 14))
        elements.append(HRFlowable(width='100%', thickness=0.5,
                                   color=colors.HexColor('#E5E7EB'), spaceAfter=8))
        elements.append(Paragraph('HISTORIAL DE PAGOS', s_sec))
        pay_rows = [['Fecha', 'Monto', 'Metodo', 'Registrado por']]
        for p in payments:
            reg = p.registered_by
            reg_name = (reg.get_full_name() or reg.username) if reg else '-'
            pay_rows.append([
                p.payment_date.strftime('%d/%m/%Y %H:%M'),
                f'${p.amount}',
                p.get_method_display(),
                reg_name,
            ])
        pay = Table(pay_rows,
                    colWidths=[3.5*cm, 2.5*cm, 3.0*cm, USABLE_W - 9*cm],
                    repeatRows=1)
        pay.setStyle(TableStyle([
            ('BACKGROUND',     (0, 0), (-1, 0),  espresso),
            ('TEXTCOLOR',      (0, 0), (-1, 0),  colors.white),
            ('FONTNAME',       (0, 0), (-1, 0),  'Helvetica-Bold'),
            ('FONTNAME',       (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE',       (0, 0), (-1, -1), 8),
            ('ALIGN',          (1, 0), (1, -1),  'RIGHT'),
            ('FONTNAME',       (1, 1), (1, -1),  'Helvetica-Bold'),
            ('TEXTCOLOR',      (1, 1), (1, -1),  colors.HexColor('#065F46')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [sand, colors.white]),
            ('GRID',           (0, 0), (-1, -1), 0.3, colors.HexColor('#DDD3C5')),
            ('TOPPADDING',     (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING',  (0, 0), (-1, -1), 4),
        ]))
        elements.append(pay)

    # ── Footer disclaimer ─────────────────────────────────────────
    elements.append(Spacer(1, 20))
    elements.append(HRFlowable(width='100%', thickness=0.5,
                               color=colors.HexColor('#E9ECEF'), spaceAfter=6))
    now_str = timezone.localtime().strftime('%d/%m/%Y %H:%M')
    elements.append(Paragraph(
        f'Documento generado el {now_str}. '
        'Este documento NO es un comprobante fiscal electronico ni una factura '
        'SRI autorizada y no tiene validez tributaria.',
        s_foot,
    ))

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
