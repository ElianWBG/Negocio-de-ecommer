import calendar
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Sum

from billing.models import Invoice

from .models import CuotaVenta, PagoCuotaVenta


def _add_months(base_date, months):
    """Suma `months` meses a base_date respetando el último día del mes destino."""
    m = base_date.month - 1 + months
    year = base_date.year + m // 12
    month = m % 12 + 1
    day = min(base_date.day, calendar.monthrange(year, month)[1])
    return base_date.replace(year=year, month=month, day=day)


def generar_cuotas(factura, numero_cuotas):
    """Crea el cronograma de cuotas mensuales de una factura de venta a
    crédito.

    La primera cuota vence 30 días después de la fecha de la factura y las
    siguientes cada 30 días. El total se reparte en centavos enteros: cada
    cuota lleva la parte base y las primeras `resto` cuotas cargan un centavo
    extra. Así la suma cuadra exacta con el total y ninguna cuota queda en
    cero (cada una vale al menos $0.01).
    """
    if numero_cuotas <= 0:
        raise ValueError('El número de cuotas debe ser mayor a cero.')
    if factura.estado == 'anulada':
        raise ValueError('No se pueden generar cuotas para una factura anulada.')
    if factura.tipo_pago != 'credito':
        raise ValueError('Solo se pueden generar cuotas para facturas a crédito.')
    if factura.cuotas.exists():
        raise ValueError('Esta factura ya tiene cuotas generadas.')
    if factura.payments.exists():
        raise ValueError(
            'Esta factura ya tiene pagos registrados; no se pueden generar cuotas.'
        )
    if factura.cobros.exists():
        raise ValueError(
            'Esta factura ya tiene cobros registrados; no se pueden generar cuotas.'
        )

    fecha_factura = factura.invoice_date.date()
    total_centavos = int((factura.total * 100).to_integral_value(rounding=ROUND_HALF_UP))
    if total_centavos < numero_cuotas:
        raise ValueError(
            'El total de la factura es muy bajo para repartirlo en esa cantidad de '
            'cuotas (cada cuota debe ser de al menos $0.01).'
        )

    base = total_centavos // numero_cuotas
    resto = total_centavos % numero_cuotas

    with transaction.atomic():
        cuotas = []
        for numero in range(1, numero_cuotas + 1):
            centavos = base + (1 if numero <= resto else 0)
            valor = Decimal(centavos) / Decimal('100')
            cuotas.append(CuotaVenta(
                factura=factura,
                numero=numero,
                fecha_vencimiento=_add_months(fecha_factura, numero),
                valor=valor,
                saldo=valor,
                estado='pendiente',
            ))
        CuotaVenta.objects.bulk_create(cuotas)

    return factura.cuotas.all()


def registrar_pago_cuota(cuota, monto, fecha, observacion=''):
    """Registra un abono sobre una cuota, actualiza su saldo/estado y
    propaga el cambio al saldo de la factura.

    Bloquea la fila de la cuota (y luego la de la factura) dentro de la
    transacción para que dos abonos concurrentes no puedan sobrepasar el
    saldo ni pisarse el saldo de la factura (lost update).
    """
    if monto <= 0:
        raise ValueError('El monto del pago debe ser mayor a cero.')

    with transaction.atomic():
        # Re-leer con lock: los checks se hacen sobre el saldo ya bloqueado.
        cuota_locked = CuotaVenta.objects.select_for_update().get(pk=cuota.pk)
        if cuota_locked.estado == 'pagada':
            raise ValueError('Esta cuota ya está pagada.')
        if monto > cuota_locked.saldo:
            raise ValueError('El monto del pago no puede ser mayor al saldo de la cuota.')

        pago = PagoCuotaVenta.objects.create(
            cuota=cuota_locked, fecha=fecha, valor=monto, observacion=observacion,
        )

        cuota_locked.saldo = cuota_locked.saldo - monto
        cuota_locked.estado = 'pagada' if cuota_locked.saldo <= 0 else 'pendiente'
        cuota_locked.save()

        factura = Invoice.objects.select_for_update().get(pk=cuota_locked.factura_id)
        verificar_factura_pagada(factura)

    # Reflejar el nuevo estado en el objeto recibido (la vista lo usa para el
    # mensaje de "saldo restante").
    cuota.saldo = cuota_locked.saldo
    cuota.estado = cuota_locked.estado
    return pago


def verificar_factura_pagada(factura):
    """Recalcula saldo y estado de la factura desde el saldo de sus cuotas.

    Fuente de verdad = suma de saldos de las cuotas (no un decremento
    incremental que puede driftear). Marca 'pagada' cuando todas las cuotas
    lo están, 'parcial' cuando ya hubo algún abono y 'pendiente' si no. Siempre
    persiste la factura.
    """
    cuotas = factura.cuotas.all()
    total_cuotas = cuotas.count()
    if not total_cuotas:
        factura.save()
        return

    pagadas = cuotas.filter(estado='pagada').count()
    saldo = cuotas.aggregate(s=Sum('saldo'))['s'] or Decimal('0.00')

    if pagadas == total_cuotas:
        factura.estado = 'pagada'
        factura.saldo = Decimal('0.00')
    elif saldo < factura.total:
        factura.estado = 'parcial'
        factura.saldo = saldo
    else:
        factura.estado = 'pendiente'
        factura.saldo = saldo
    factura.save()
