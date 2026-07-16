from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Sum

from purchasing.models import Purchase

from .models import CuotaCompra, PagoCuotaCompra


def generar_cuotas(compra, numero_cuotas):
    """Crea el cronograma de cuotas mensuales de una compra a crédito.

    La primera cuota vence 30 días después de la compra y las siguientes
    cada 30 días. El total se reparte en centavos enteros: cada cuota lleva
    la parte base y las primeras `resto` cuotas cargan un centavo extra. Así
    la suma cuadra exacta con el total y ninguna cuota queda en cero (cada
    una vale al menos $0.01).
    """
    if numero_cuotas <= 0:
        raise ValueError('El número de cuotas debe ser mayor a cero.')
    if compra.estado == 'anulada':
        raise ValueError('No se pueden generar cuotas para una compra anulada.')
    if compra.tipo_pago != 'credito':
        raise ValueError('Solo se pueden generar cuotas para compras a crédito.')
    if compra.cuotas.exists():
        raise ValueError('Esta compra ya tiene cuotas generadas.')
    if compra.pagos.exists():
        raise ValueError(
            'Esta compra ya tiene pagos registrados por el módulo de pagos; '
            'no se pueden generar cuotas.'
        )

    fecha_compra = compra.purchase_date.date()
    total_centavos = int((compra.total * 100).to_integral_value(rounding=ROUND_HALF_UP))
    if total_centavos < numero_cuotas:
        raise ValueError(
            'El total de la compra es muy bajo para repartirlo en esa cantidad de '
            'cuotas (cada cuota debe ser de al menos $0.01).'
        )

    base = total_centavos // numero_cuotas
    resto = total_centavos % numero_cuotas

    with transaction.atomic():
        cuotas = []
        for numero in range(1, numero_cuotas + 1):
            centavos = base + (1 if numero <= resto else 0)
            valor = Decimal(centavos) / Decimal('100')
            cuotas.append(CuotaCompra(
                compra=compra,
                numero=numero,
                fecha_vencimiento=fecha_compra + timedelta(days=30 * numero),
                valor=valor,
                saldo=valor,
                estado='pendiente',
            ))
        CuotaCompra.objects.bulk_create(cuotas)

    return compra.cuotas.all()


def registrar_pago_cuota(cuota, monto, fecha, observacion=''):
    """Registra un abono sobre una cuota, actualiza su saldo/estado y
    propaga el cambio al saldo de la compra.

    Bloquea la fila de la cuota (y luego la de la compra) dentro de la
    transacción para que dos abonos concurrentes no puedan sobrepasar el
    saldo ni pisarse el saldo de la compra (lost update).
    """
    if monto <= 0:
        raise ValueError('El monto del pago debe ser mayor a cero.')

    with transaction.atomic():
        # Re-leer con lock: los checks se hacen sobre el saldo ya bloqueado.
        cuota_locked = CuotaCompra.objects.select_for_update().get(pk=cuota.pk)
        if cuota_locked.estado == 'pagada':
            raise ValueError('Esta cuota ya está pagada.')
        if monto > cuota_locked.saldo:
            raise ValueError('El monto del pago no puede ser mayor al saldo de la cuota.')

        pago = PagoCuotaCompra.objects.create(
            cuota=cuota_locked, fecha=fecha, valor=monto, observacion=observacion,
        )

        cuota_locked.saldo = cuota_locked.saldo - monto
        cuota_locked.estado = 'pagada' if cuota_locked.saldo <= 0 else 'pendiente'
        cuota_locked.save()

        compra = Purchase.objects.select_for_update().get(pk=cuota_locked.compra_id)
        verificar_compra_pagada(compra)

    # Reflejar el nuevo estado en el objeto recibido (la vista lo usa para el
    # mensaje de "saldo restante").
    cuota.saldo = cuota_locked.saldo
    cuota.estado = cuota_locked.estado
    return pago


def verificar_compra_pagada(compra):
    """Recalcula saldo y estado de la compra desde el saldo de sus cuotas.

    Fuente de verdad = suma de saldos de las cuotas (no un decremento
    incremental que puede driftear). Marca 'pagada' cuando todas las cuotas
    lo están, 'parcial' cuando ya hubo algún abono y 'pendiente' si no. Siempre
    persiste la compra.
    """
    cuotas = compra.cuotas.all()
    total_cuotas = cuotas.count()
    if not total_cuotas:
        compra.save()
        return

    pagadas = cuotas.filter(estado='pagada').count()
    saldo = cuotas.aggregate(s=Sum('saldo'))['s'] or Decimal('0.00')

    if pagadas == total_cuotas:
        compra.estado = 'pagada'
        compra.saldo = Decimal('0.00')
    elif saldo < compra.total:
        compra.estado = 'parcial'
        compra.saldo = saldo
    else:
        compra.estado = 'pendiente'
        compra.saldo = saldo
    compra.save()
