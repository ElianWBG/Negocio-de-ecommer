from datetime import timedelta

from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from purchasing.models import Purchase
from shared.decorators import permission_required_any

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

    if supplier := g.get('supplier', '').strip():
        cuotas = cuotas.filter(compra__supplier__name__icontains=supplier)
    if date_from := g.get('date_from', '').strip():
        cuotas = cuotas.filter(fecha_vencimiento__gte=date_from)
    if date_to := g.get('date_to', '').strip():
        cuotas = cuotas.filter(fecha_vencimiento__lte=date_to)

    cuotas = cuotas.order_by('fecha_vencimiento')
    hoy = timezone.localdate()
    total_pendiente = sum(c.saldo for c in cuotas.filter(estado='pendiente'))

    return render(request, 'creditos_compras/cuotas_pendientes_list.html', {
        'cuotas': cuotas,
        'hoy': hoy,
        'limite_proximo': hoy + timedelta(days=7),
        'total_pendiente': total_pendiente,
        'estado_filtro': estado,
    })
