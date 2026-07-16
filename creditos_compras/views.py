from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from billing.models import Supplier
from purchasing.models import Purchase
from shared.decorators import permission_required_any
from shared.validators import parse_date_param

from .forms import GenerarCuotasForm, PagoCuotaCompraForm
from .models import CuotaCompra
from .services import generar_cuotas, registrar_pago_cuota


@permission_required_any('creditos_compras.add_cuotacompra')
def generar_cuotas_view(request, compra_id):
    """Genera el cronograma de cuotas de una compra a crédito (una sola vez)."""
    compra = get_object_or_404(Purchase, pk=compra_id)

    if compra.tipo_pago != 'credito':
        messages.error(request, 'Solo las compras a crédito pueden tener cuotas.')
        return redirect('purchasing:purchase_detail', pk=compra.id)

    if compra.cuotas.exists():
        messages.error(request, 'Esta compra ya tiene cuotas generadas.')
        return redirect('creditos_compras:cuota_list', compra_id=compra.id)

    if compra.pagos.exists():
        messages.error(
            request,
            'Esta compra ya tiene pagos registrados por el módulo de pagos; '
            'no se pueden generar cuotas.'
        )
        return redirect('pagos:payment_history', compra_id=compra.id)

    if request.method == 'POST':
        form = GenerarCuotasForm(request.POST)
        if form.is_valid():
            numero_cuotas = form.cleaned_data['numero_cuotas']
            try:
                generar_cuotas(compra, numero_cuotas)
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(
                    request,
                    f'Se generaron {numero_cuotas} cuotas para la compra #{compra.id}.'
                )
                return redirect('creditos_compras:cuota_list', compra_id=compra.id)
    else:
        form = GenerarCuotasForm()

    return render(request, 'creditos_compras/generar_cuotas.html', {
        'form': form, 'compra': compra,
    })


@permission_required_any('creditos_compras.view_cuotacompra')
def cuota_list(request, compra_id):
    """Lista las cuotas de una compra con su resumen de saldo."""
    compra = get_object_or_404(Purchase.objects.select_related('supplier'), pk=compra_id)
    cuotas = compra.cuotas.all()

    return render(request, 'creditos_compras/cuota_list.html', {
        'compra': compra,
        'cuotas': cuotas,
        'cuotas_pendientes': cuotas.filter(estado='pendiente').count(),
        'cuotas_pagadas': cuotas.filter(estado='pagada').count(),
        'hoy': timezone.localdate(),
    })


@permission_required_any('creditos_compras.add_pagocuotacompra')
def pago_cuota_create(request, pk):
    """Registra un nuevo abono sobre una cuota específica."""
    cuota = get_object_or_404(CuotaCompra.objects.select_related('compra'), pk=pk)

    if cuota.estado == 'pagada':
        messages.error(request, 'Esta cuota ya está pagada.')
        return redirect('creditos_compras:cuota_payment_history', pk=cuota.pk)

    if request.method == 'POST':
        form = PagoCuotaCompraForm(request.POST, initial={'cuota': cuota})
        if form.is_valid():
            registrar_pago_cuota(
                cuota,
                form.cleaned_data['valor'],
                form.cleaned_data['fecha'],
                form.cleaned_data.get('observacion', ''),
            )
            messages.success(
                request,
                f'Pago registrado. Saldo restante de la cuota: ${cuota.saldo}'
            )
            return redirect('creditos_compras:cuota_payment_history', pk=cuota.pk)
    else:
        form = PagoCuotaCompraForm(initial={
            'cuota': cuota, 'valor': cuota.saldo, 'fecha': timezone.localdate(),
        })

    return render(request, 'creditos_compras/pago_form.html', {
        'form': form, 'cuota': cuota,
    })


@permission_required_any('creditos_compras.add_pagocuotacompra')
def pagar_cuotas_multi(request, compra_id):
    """Registra el pago de VARIAS cuotas pendientes de una compra en un
    solo envío (ej. pagar 2, 4 o todas de golpe). Cada cuota seleccionada
    se paga por el monto indicado (por defecto, su saldo completo)."""
    compra = get_object_or_404(Purchase.objects.select_related('supplier'), pk=compra_id)
    cuotas_pendientes = compra.cuotas.filter(estado='pendiente').order_by('numero')

    if not cuotas_pendientes.exists():
        messages.info(request, 'Esta compra no tiene cuotas pendientes.')
        return redirect('creditos_compras:cuota_list', compra_id=compra.id)

    if request.method == 'POST':
        seleccionadas = request.POST.getlist('cuotas')
        observacion = request.POST.get('observacion', '').strip()
        fecha_raw = request.POST.get('fecha', '')
        try:
            fecha_pago = datetime.strptime(fecha_raw, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, 'Indica una fecha de pago válida.')
            return redirect('creditos_compras:pagar_cuotas_multi', compra_id=compra.id)

        if not seleccionadas:
            messages.error(request, 'Selecciona al menos una cuota para pagar.')
        else:
            pagadas = 0
            total_pagado = Decimal('0.00')
            errores = []
            with transaction.atomic():
                for cuota_id in seleccionadas:
                    cuota = CuotaCompra.objects.filter(pk=cuota_id, compra=compra).first()
                    if cuota is None:
                        continue
                    monto_raw = request.POST.get(f'monto_{cuota_id}', '').strip()
                    try:
                        monto = Decimal(monto_raw) if monto_raw else cuota.saldo
                    except InvalidOperation:
                        errores.append(f'Cuota {cuota.numero}: monto inválido.')
                        continue
                    try:
                        registrar_pago_cuota(cuota, monto, fecha_pago, observacion)
                    except ValueError as e:
                        errores.append(f'Cuota {cuota.numero}: {e}')
                    else:
                        pagadas += 1
                        total_pagado += monto

            for error in errores:
                messages.error(request, error)
            if pagadas:
                messages.success(
                    request,
                    f'Se registraron {pagadas} pago(s) por un total de ${total_pagado}.'
                )
                return redirect('creditos_compras:cuota_list', compra_id=compra.id)

    return render(request, 'creditos_compras/pagar_cuotas_multi.html', {
        'compra': compra,
        'cuotas': cuotas_pendientes,
        'hoy': timezone.localdate(),
    })


@permission_required_any('creditos_compras.view_pagocuotacompra')
def cuota_payment_history(request, pk):
    """Historial de pagos de una cuota."""
    cuota = get_object_or_404(CuotaCompra.objects.select_related('compra', 'compra__supplier'), pk=pk)
    pagos = cuota.pagos.all()
    total_pagado = sum(p.valor for p in pagos)

    return render(request, 'creditos_compras/payment_history.html', {
        'cuota': cuota, 'pagos': pagos, 'total_pagado': total_pagado,
    })


@permission_required_any('creditos_compras.view_cuotacompra')
def cuotas_pendientes_list(request):
    """Dashboard de cuotas de todas las compras, con filtros."""
    cuotas = CuotaCompra.objects.select_related('compra', 'compra__supplier')

    g = request.GET
    estado = g.get('estado', 'pendiente')
    if estado in ('pendiente', 'pagada'):
        cuotas = cuotas.filter(estado=estado)

    if (supplier := g.get('supplier', '').strip()) and supplier.isdigit():
        cuotas = cuotas.filter(compra__supplier_id=supplier)
    if parsed_from := parse_date_param(g.get('date_from', '')):
        cuotas = cuotas.filter(fecha_vencimiento__gte=parsed_from)
    if parsed_to := parse_date_param(g.get('date_to', '')):
        cuotas = cuotas.filter(fecha_vencimiento__lte=parsed_to)

    cuotas = cuotas.order_by('fecha_vencimiento')
    hoy = timezone.localdate()
    total_pendiente = sum(c.saldo for c in cuotas.filter(estado='pendiente'))

    return render(request, 'creditos_compras/cuotas_pendientes_list.html', {
        'cuotas': cuotas,
        'hoy': hoy,
        'limite_proximo': hoy + timedelta(days=7),
        'total_pendiente': total_pendiente,
        'estado_filtro': estado,
        'suppliers': Supplier.objects.order_by('name'),
    })
