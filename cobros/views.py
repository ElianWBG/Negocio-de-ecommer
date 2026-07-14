from django.contrib import messages
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404

from billing.models import Invoice
from shared.decorators import permission_required_any
from .forms import CobroFacturaForm
from .models import CobroFactura


# =============================================
# MÓDULO DE COBROS (cuentas por cobrar)
# =============================================

@permission_required_any('cobros.view_cobrofactura')
def invoice_pending_list(request):
    """Lista únicamente las facturas a crédito que aún tienen saldo pendiente.

    Las facturas que ya tienen un cronograma de cuotas generado (app
    creditos_ventas) se excluyen de aquí: sus pagos se registran por
    cuota, no como abono libre contra el saldo total.
    """
    # Incluye 'parcial': facturas con un abono previo siguen teniendo saldo
    # y deben permitir registrar cobros adicionales.
    invoices = Invoice.objects.filter(
        tipo_pago='credito', estado__in=('pendiente', 'parcial')
    ).exclude(cuotas__isnull=False).select_related('customer').order_by('-invoice_date')

    g = request.GET
    if customer := g.get('customer', '').strip():
        invoices = (invoices.filter(customer__first_name__icontains=customer) |
                    invoices.filter(customer__last_name__icontains=customer))

    return render(request, 'cobros/invoice_pending_list.html', {'invoices': invoices})


@permission_required_any('cobros.add_cobrofactura')
def cobro_create(request, factura_id):
    """Registra un nuevo abono sobre una factura específica."""
    factura = get_object_or_404(Invoice, pk=factura_id)

    if factura.estado == 'anulada':
        messages.error(request, 'No se puede registrar un pago sobre una factura anulada.')
        return redirect('cobros:invoice_pending_list')

    if factura.cuotas.exists():
        messages.error(
            request,
            'Esta factura tiene un cronograma de cuotas generado. '
            'Registra los pagos desde el módulo de cuotas.'
        )
        return redirect('creditos_ventas:cuota_list', factura_id=factura.id)

    if request.method == 'POST':
        form = CobroFacturaForm(request.POST, initial={'factura': factura})
        if form.is_valid():
            with transaction.atomic():
                cobro = form.save(commit=False)
                factura = Invoice.objects.select_for_update().get(pk=factura_id)
                if cobro.valor > factura.saldo:
                    messages.error(request, f'El monto (${cobro.valor}) supera el saldo actual (${factura.saldo}). Otro pago pudo haberse registrado simultáneamente.')
                    return redirect('cobros:cobro_create', factura_id=factura_id)
                cobro.save()
                factura.saldo = factura.saldo - cobro.valor
                if factura.saldo <= 0:
                    factura.estado = 'pagada'
                elif factura.saldo < factura.total:
                    factura.estado = 'parcial'
                else:
                    factura.estado = 'pendiente'
                factura.save()
            messages.success(request, f'Pago de ${cobro.valor} registrado. Saldo restante: ${factura.saldo}')
            return redirect('cobros:payment_history', factura_id=factura.id)
    else:
        form = CobroFacturaForm(initial={'factura': factura, 'valor': factura.saldo})

    return render(request, 'cobros/cobro_form.html', {
        'form': form, 'factura': factura, 'title': 'Registrar pago',
    })


@permission_required_any('cobros.view_cobrofactura')
def payment_history(request, factura_id):
    """Muestra el historial de pagos de una factura y su saldo actual."""
    factura = get_object_or_404(Invoice, pk=factura_id)
    cobros = factura.cobros.all()
    total_pagado = sum(c.valor for c in cobros)
    return render(request, 'cobros/payment_history.html', {
        'factura': factura, 'cobros': cobros, 'total_pagado': total_pagado,
    })


@permission_required_any('cobros.change_cobrofactura')
def cobro_update(request, pk):
    """Edita un cobro ya registrado, recalculando el saldo de la factura."""
    cobro = get_object_or_404(CobroFactura, pk=pk)
    factura = cobro.factura
    valor_anterior = cobro.valor  # capturado ANTES de construir el form: is_valid()
                                    # muta el objeto `cobro` con los valores nuevos,
                                    # así que si lo leyéramos después ya estaría pisado.

    if factura.estado == 'anulada':
        messages.error(request, 'No se puede editar un pago de una factura anulada.')
        return redirect('cobros:payment_history', factura_id=factura.id)

    if request.method == 'POST':
        form = CobroFacturaForm(request.POST, instance=cobro)
        if form.is_valid():
            with transaction.atomic():
                cobro_actualizado = form.save(commit=False)
                factura = Invoice.objects.select_for_update().get(pk=factura.pk)
                nuevo_saldo = factura.saldo + valor_anterior - cobro_actualizado.valor
                if nuevo_saldo < 0:
                    messages.error(request, f'El nuevo monto (${cobro_actualizado.valor}) excede el saldo disponible. Otro pago pudo haber sido registrado simultáneamente.')
                    return redirect('cobros:cobro_update', pk=cobro_actualizado.pk)
                factura.saldo = nuevo_saldo
                if factura.saldo <= 0:
                    factura.estado = 'pagada'
                elif factura.saldo < factura.total:
                    factura.estado = 'parcial'
                else:
                    factura.estado = 'pendiente'
                factura.save()
                cobro_actualizado.save()
            messages.success(request, 'Pago actualizado correctamente.')
            return redirect('cobros:payment_history', factura_id=factura.id)
    else:
        form = CobroFacturaForm(instance=cobro)

    return render(request, 'cobros/cobro_form.html', {
        'form': form, 'factura': factura, 'title': 'Editar pago',
    })


@permission_required_any('cobros.delete_cobrofactura')
def cobro_delete(request, pk):
    """Elimina un cobro, reponiendo su valor al saldo de la factura.
    No se permite si la factura está anulada."""
    cobro = get_object_or_404(CobroFactura, pk=pk)
    factura = cobro.factura

    if factura.estado == 'anulada':
        messages.error(request, 'No se puede eliminar un pago de una factura anulada.')
        return redirect('cobros:payment_history', factura_id=factura.id)

    if request.method == 'POST':
        with transaction.atomic():
            factura = Invoice.objects.select_for_update().get(pk=factura.pk)
            factura.saldo = factura.saldo + cobro.valor
            if factura.saldo <= 0:
                factura.estado = 'pagada'
            elif factura.saldo < factura.total:
                factura.estado = 'parcial'
            else:
                factura.estado = 'pendiente'
            factura.save()
            cobro.delete()
        messages.success(request, 'Pago eliminado y saldo repuesto.')
        return redirect('cobros:payment_history', factura_id=factura.id)

    return render(request, 'cobros/cobro_confirm_delete.html', {'cobro': cobro, 'factura': factura})
