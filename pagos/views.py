from django.contrib import messages
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404

from billing.models import Supplier
from purchasing.models import Purchase
from shared.decorators import permission_required_any
from .forms import PagoCompraForm
from .models import PagoCompra


# =============================================
# MÓDULO DE PAGOS (cuentas por pagar)
# =============================================

@permission_required_any('pagos.view_pagocompra')
def purchase_pending_list(request):
    """Lista únicamente las compras a crédito que aún tienen saldo pendiente.

    Las compras que ya tienen un cronograma de cuotas generado (app
    creditos_compras) se excluyen de aquí: sus pagos se registran por
    cuota, no como abono libre contra el saldo total.
    """
    purchases = Purchase.objects.filter(
        tipo_pago='credito', estado='pendiente'
    ).exclude(cuotas__isnull=False).select_related('supplier').order_by('-purchase_date')

    g = request.GET
    if supplier := g.get('supplier', '').strip():
        purchases = purchases.filter(supplier_id=supplier)

    return render(request, 'pagos/purchase_pending_list.html', {
        'purchases': purchases,
        'suppliers': Supplier.objects.order_by('name'),
    })


@permission_required_any('pagos.add_pagocompra')
def pago_create(request, compra_id):
    """Registra un nuevo abono sobre una compra específica."""
    compra = get_object_or_404(Purchase, pk=compra_id)

    if compra.estado == 'anulada':
        messages.error(request, 'No se puede registrar un pago sobre una compra anulada.')
        return redirect('pagos:purchase_pending_list')

    if compra.cuotas.exists():
        messages.error(
            request,
            'Esta compra tiene un cronograma de cuotas generado. '
            'Registra los pagos desde el módulo de cuotas.'
        )
        return redirect('creditos_compras:cuota_list', compra_id=compra.id)

    if request.method == 'POST':
        form = PagoCompraForm(request.POST, initial={'compra': compra})
        if form.is_valid():
            with transaction.atomic():
                pago = form.save()
                compra.saldo = compra.saldo - pago.valor
                compra.estado = 'pagada' if compra.saldo <= 0 else 'pendiente'
                compra.save()
            messages.success(request, f'Pago de ${pago.valor} registrado. Saldo restante: ${compra.saldo}')
            return redirect('pagos:payment_history', compra_id=compra.id)
    else:
        form = PagoCompraForm(initial={'compra': compra, 'valor': compra.saldo})

    return render(request, 'pagos/pago_form.html', {
        'form': form, 'compra': compra, 'title': 'Registrar pago',
    })


@permission_required_any('pagos.view_pagocompra')
def payment_history(request, compra_id):
    """Historial de pagos de una compra y su saldo actual."""
    compra = get_object_or_404(Purchase, pk=compra_id)
    pagos = compra.pagos.all()
    total_pagado = sum(p.valor for p in pagos)
    return render(request, 'pagos/payment_history.html', {
        'compra': compra, 'pagos': pagos, 'total_pagado': total_pagado,
    })


@permission_required_any('pagos.change_pagocompra')
def pago_update(request, pk):
    """Edita un pago ya registrado, recalculando el saldo de la compra."""
    pago = get_object_or_404(PagoCompra, pk=pk)
    compra = pago.compra
    valor_anterior = pago.valor  # capturado ANTES de construir el form (ver nota en cobros/views.py)

    if compra.estado == 'anulada':
        messages.error(request, 'No se puede editar un pago de una compra anulada.')
        return redirect('pagos:payment_history', compra_id=compra.id)

    if request.method == 'POST':
        form = PagoCompraForm(request.POST, instance=pago)
        if form.is_valid():
            with transaction.atomic():
                pago_actualizado = form.save(commit=False)
                compra.saldo = compra.saldo + valor_anterior - pago_actualizado.valor
                compra.estado = 'pagada' if compra.saldo <= 0 else 'pendiente'
                compra.save()
                pago_actualizado.save()
            messages.success(request, 'Pago actualizado correctamente.')
            return redirect('pagos:payment_history', compra_id=compra.id)
    else:
        form = PagoCompraForm(instance=pago)

    return render(request, 'pagos/pago_form.html', {
        'form': form, 'compra': compra, 'title': 'Editar pago',
    })


@permission_required_any('pagos.delete_pagocompra')
def pago_delete(request, pk):
    """Elimina un pago, reponiendo su valor al saldo de la compra."""
    pago = get_object_or_404(PagoCompra, pk=pk)
    compra = pago.compra

    if compra.estado == 'anulada':
        messages.error(request, 'No se puede eliminar un pago de una compra anulada.')
        return redirect('pagos:payment_history', compra_id=compra.id)

    if request.method == 'POST':
        with transaction.atomic():
            compra.saldo = compra.saldo + pago.valor
            compra.estado = 'pendiente'
            compra.save()
            pago.delete()
        messages.success(request, 'Pago eliminado y saldo repuesto.')
        return redirect('pagos:payment_history', compra_id=compra.id)

    return render(request, 'pagos/pago_confirm_delete.html', {'pago': pago, 'compra': compra})
