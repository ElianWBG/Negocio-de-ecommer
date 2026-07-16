from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Sum

from purchasing.models import Purchase

from .models import CuotaCompra, PagoCuotaCompra


def generar_cuotas(compra, numero_cuotas):
    """Crea el cronograma de cuotas mensuales de una compra a crédito.

    La primera cuota vence 30 días después de la compra y las siguientes
    cada 30 días. El total se reparte equitativamente entre las cuotas;
    la última cuota absorbe el céntimo de redondeo para que la suma de
    las cuotas cuadre exactamente con el total de la compra.
    """
    if numero_cuotas <= 0:
        raise ValueError('El número de cuotas debe ser mayor a cero.')
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
    valor_cuota = (compra.total / numero_cuotas).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    with transaction.atomic():
        acumulado = Decimal('0.00')
        cuotas = []
        for numero in range(1, numero_cuotas + 1):
            if numero < numero_cuotas:
                valor = valor_cuota
                acumulado += valor
            else:
                valor = compra.total - acumulado  # última cuota: absorbe el redondeo
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
