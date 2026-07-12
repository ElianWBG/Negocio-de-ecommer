from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction

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
    propaga el cambio al saldo de la compra."""
    if monto <= 0:
        raise ValueError('El monto del pago debe ser mayor a cero.')
    if monto > cuota.saldo:
        raise ValueError('El monto del pago no puede ser mayor al saldo de la cuota.')

    with transaction.atomic():
        pago = PagoCuotaCompra.objects.create(
            cuota=cuota, fecha=fecha, valor=monto, observacion=observacion,
        )

        cuota.saldo = cuota.saldo - monto
        cuota.estado = 'pagada' if cuota.saldo <= 0 else 'pendiente'
        cuota.save()

        compra = cuota.compra
        compra.saldo = compra.saldo - monto
        verificar_compra_pagada(compra)

    return pago


def verificar_compra_pagada(compra):
    """Revisa si todas las cuotas de la compra están pagadas y, de ser
    así, marca la compra como pagada. Siempre persiste la compra."""
    if not compra.cuotas.exclude(estado='pagada').exists():
        compra.estado = 'pagada'
        compra.saldo = Decimal('0.00')
    compra.save()
