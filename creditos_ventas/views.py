from datetime import timedelta

from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from billing.models import Invoice, Customer
from shared.decorators import permission_required_any

from .forms import GenerarCuotasForm, PagoCuotaVentaForm
from .models import CuotaVenta
from .services import generar_cuotas, registrar_pago_cuota


def comprobante_cuota(request, pk):
    """Comprobante único e imprimible de una cuota: accesible por el cliente
    dueño de la factura, o por el staff con permiso de ver cuotas."""
    cuota = get_object_or_404(
        CuotaVenta.objects.select_related('factura', 'factura__customer'), pk=pk
    )
    user = request.user
    is_owner = hasattr(user, 'customer_profile') and user.customer_profile.pk == cuota.factura.customer_id
    is_staff_viewer = user.is_authenticated and (user.is_superuser or user.has_perm('creditos_ventas.view_cuotaventa'))

    if not (is_owner or is_staff_viewer):
        from django.urls import reverse
        request.session['next_after_login'] = reverse('creditos_ventas:comprobante_cuota', args=[cuota.pk])
        messages.info(request, 'Inicia sesión para ver tu comprobante.')
        return redirect('storefront:customer_login')

    codigo = f'CV-{cuota.factura_id:05d}-{cuota.numero:02d}'
    total_cuotas = cuota.factura.cuotas.count()

    return render(request, 'creditos_ventas/comprobante_cuota.html', {
        'cuota': cuota, 'codigo': codigo, 'total_cuotas': total_cuotas,
    })


@permission_required_any('creditos_ventas.add_cuotaventa')
def generar_cuotas_view(request, factura_id):
    """Genera el cronograma de cuotas de una factura a crédito (una sola vez)."""
    factura = get_object_or_404(Invoice, pk=factura_id)

    if factura.tipo_pago != 'credito':
        messages.error(request, 'Solo las facturas a crédito pueden tener cuotas.')
        return redirect('billing:invoice_detail', pk=factura.id)

    if factura.cuotas.exists():
        messages.error(request, 'Esta factura ya tiene cuotas generadas.')
        return redirect('creditos_ventas:cuota_list', factura_id=factura.id)

    if factura.payments.exists() or factura.cobros.exists():
        messages.error(
            request,
            'Esta factura ya tiene pagos registrados; no se pueden generar cuotas.'
        )
        return redirect('billing:invoice_detail', pk=factura.id)

    if request.method == 'POST':
        form = GenerarCuotasForm(request.POST)
        if form.is_valid():
            numero_cuotas = form.cleaned_data['numero_cuotas']
            try:
                generar_cuotas(factura, numero_cuotas)
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(
                    request,
                    f'Se generaron {numero_cuotas} cuotas para la factura #{factura.id}.'
                )
                return redirect('creditos_ventas:cuota_list', factura_id=factura.id)
    else:
        form = GenerarCuotasForm()

    return render(request, 'creditos_ventas/generar_cuotas.html', {
        'form': form, 'factura': factura,
    })


@permission_required_any('creditos_ventas.view_cuotaventa')
def cuota_list(request, factura_id):
    """Lista las cuotas de una factura con su resumen de saldo."""
    factura = get_object_or_404(Invoice.objects.select_related('customer'), pk=factura_id)
    cuotas = factura.cuotas.all()

    return render(request, 'creditos_ventas/cuota_list.html', {
        'factura': factura,
        'cuotas': cuotas,
        'cuotas_pendientes': cuotas.filter(estado='pendiente').count(),
        'cuotas_pagadas': cuotas.filter(estado='pagada').count(),
        'hoy': timezone.localdate(),
    })


@permission_required_any('creditos_ventas.add_pagocuotaventa')
def pago_cuota_create(request, pk):
    """Registra un nuevo abono sobre una cuota específica."""
    cuota = get_object_or_404(CuotaVenta.objects.select_related('factura'), pk=pk)

    if cuota.estado == 'pagada':
        messages.error(request, 'Esta cuota ya está pagada.')
        return redirect('creditos_ventas:cuota_payment_history', pk=cuota.pk)

    if request.method == 'POST':
        form = PagoCuotaVentaForm(request.POST, initial={'cuota': cuota})
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
            return redirect('creditos_ventas:cuota_payment_history', pk=cuota.pk)
    else:
        form = PagoCuotaVentaForm(initial={
            'cuota': cuota, 'valor': cuota.saldo, 'fecha': timezone.localdate(),
        })

    return render(request, 'creditos_ventas/pago_form.html', {
        'form': form, 'cuota': cuota,
    })


@permission_required_any('creditos_ventas.view_pagocuotaventa')
def cuota_payment_history(request, pk):
    """Historial de pagos de una cuota."""
    cuota = get_object_or_404(CuotaVenta.objects.select_related('factura', 'factura__customer'), pk=pk)
    pagos = cuota.pagos.all()
    total_pagado = sum(p.valor for p in pagos)

    return render(request, 'creditos_ventas/payment_history.html', {
        'cuota': cuota, 'pagos': pagos, 'total_pagado': total_pagado,
    })


@permission_required_any('creditos_ventas.view_cuotaventa')
def cuotas_pendientes_list(request):
    """Dashboard de cuotas de todas las facturas, con filtros."""
    cuotas = CuotaVenta.objects.select_related('factura', 'factura__customer')

    g = request.GET
    estado = g.get('estado', 'pendiente')
    if estado in ('pendiente', 'pagada'):
        cuotas = cuotas.filter(estado=estado)

    if customer := g.get('customer', '').strip():
        cuotas = cuotas.filter(factura__customer_id=customer)
    if date_from := g.get('date_from', '').strip():
        cuotas = cuotas.filter(fecha_vencimiento__gte=date_from)
    if date_to := g.get('date_to', '').strip():
        cuotas = cuotas.filter(fecha_vencimiento__lte=date_to)

    cuotas = cuotas.order_by('fecha_vencimiento')
    hoy = timezone.localdate()
    total_pendiente = sum(c.saldo for c in cuotas.filter(estado='pendiente'))

    return render(request, 'creditos_ventas/cuotas_pendientes_list.html', {
        'cuotas': cuotas,
        'hoy': hoy,
        'limite_proximo': hoy + timedelta(days=7),
        'total_pendiente': total_pendiente,
        'estado_filtro': estado,
        'customers': Customer.objects.order_by('first_name', 'last_name'),
    })
