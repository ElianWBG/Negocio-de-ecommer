from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction

from .models import CuotaVenta, PagoCuotaVenta


def generar_cuotas(factura, numero_cuotas):
    """Crea el cronograma de cuotas mensuales de una factura de venta a
    crédito.

    La primera cuota vence 30 días después de la fecha de la factura y las
    siguientes cada 30 días. El total se reparte equitativamente entre las
    cuotas; la última cuota absorbe el céntimo de redondeo para que la suma
    de las cuotas cuadre exactamente con el total de la factura.
    """
    if numero_cuotas <= 0:
        raise ValueError('El número de cuotas debe ser mayor a cero.')
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
    valor_cuota = (factura.total / numero_cuotas).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    with transaction.atomic():
        acumulado = Decimal('0.00')
        cuotas = []
        for numero in range(1, numero_cuotas + 1):
            if numero < numero_cuotas:
                valor = valor_cuota
                acumulado += valor
            else:
                valor = factura.total - acumulado  # última cuota: absorbe el redondeo
            cuotas.append(CuotaVenta(
                factura=factura,
                numero=numero,
                fecha_vencimiento=fecha_factura + timedelta(days=30 * numero),
                valor=valor,
                saldo=valor,
                estado='pendiente',
            ))
        CuotaVenta.objects.bulk_create(cuotas)

    return factura.cuotas.all()


def registrar_pago_cuota(cuota, monto, fecha, observacion=''):
    """Registra un abono sobre una cuota, actualiza su saldo/estado y
    propaga el cambio al saldo de la factura."""
    if monto <= 0:
        raise ValueError('El monto del pago debe ser mayor a cero.')
    if monto > cuota.saldo:
        raise ValueError('El monto del pago no puede ser mayor al saldo de la cuota.')

    with transaction.atomic():
        pago = PagoCuotaVenta.objects.create(
            cuota=cuota, fecha=fecha, valor=monto, observacion=observacion,
        )

        cuota.saldo = cuota.saldo - monto
        cuota.estado = 'pagada' if cuota.saldo <= 0 else 'pendiente'
        cuota.save()

        factura = cuota.factura
        factura.saldo = factura.saldo - monto
        verificar_factura_pagada(factura)

    return pago


def verificar_factura_pagada(factura):
    """Revisa si todas las cuotas de la factura están pagadas y, de ser
    así, marca la factura como pagada. Siempre persiste la factura."""
    if not factura.cuotas.exclude(estado='pagada').exists():
        factura.estado = 'pagada'
        factura.saldo = Decimal('0.00')
    factura.save()
