from decimal import Decimal
from django.db import transaction
from django.db.models import Sum


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
