from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404

from purchasing.models import Purchase
from .forms import PagoCompraForm
from .models import PagoCompra


# =============================================
# MÓDULO DE PAGOS (cuentas por pagar)
# =============================================

@login_required
def purchase_pending_list(request):
    """Lista únicamente las compras a crédito que aún tienen saldo pendiente."""
    purchases = Purchase.objects.filter(
        tipo_pago='credito', estado='pendiente'
    ).select_related('supplier').order_by('-purchase_date')

    g = request.GET
    if supplier := g.get('supplier', '').strip():
        purchases = purchases.filter(supplier__name__icontains=supplier)

    return render(request, 'pagos/purchase_pending_list.html', {'purchases': purchases})


@login_required
def pago_create(request, compra_id):
    """Registra un nuevo abono sobre una compra específica."""
    compra = get_object_or_404(Purchase, pk=compra_id)

    if compra.estado == 'anulada':
        messages.error(request, 'No se puede registrar un pago sobre una compra anulada.')
        return redirect('pagos:purchase_pending_list')

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


@login_required
def payment_history(request, compra_id):
    """Historial de pagos de una compra y su saldo actual."""
    compra = get_object_or_404(Purchase, pk=compra_id)
    pagos = compra.pagos.all()
    total_pagado = sum(p.valor for p in pagos)
    return render(request, 'pagos/payment_history.html', {
        'compra': compra, 'pagos': pagos, 'total_pagado': total_pagado,
    })


@login_required
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


@login_required
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
