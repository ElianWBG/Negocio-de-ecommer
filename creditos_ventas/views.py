import json
import logging
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from billing.models import Invoice, Customer
from shared.decorators import permission_required_any
from shared.paypal_client import paypal_access_token, paypal_request

from .forms import GenerarCuotasForm, PagoCuotaVentaForm
from .models import CuotaVenta, PagoCuotaVenta
from .services import generar_cuotas, registrar_pago_cuota

logger = logging.getLogger(__name__)


def _es_dueno_o_staff(request, factura):
    """Devuelve (autorizado, es_dueno) para una factura: dueño (cliente
    autenticado con customer_profile == factura.customer) o staff con
    permiso de ver cuotas/pagos."""
    user = request.user
    is_owner = hasattr(user, 'customer_profile') and user.customer_profile.pk == factura.customer_id
    is_staff_viewer = user.is_authenticated and (
        user.is_superuser
        or user.has_perm('creditos_ventas.view_cuotaventa')
        or user.has_perm('creditos_ventas.view_pagocuotaventa')
    )
    return (is_owner or is_staff_viewer), is_owner


def comprobante_cuota(request, pk):
    """Comprobante único e imprimible de una cuota: accesible por el cliente
    dueño de la factura, o por el staff con permiso de ver cuotas."""
    cuota = get_object_or_404(
        CuotaVenta.objects.select_related('factura', 'factura__customer'), pk=pk
    )
    autorizado, is_owner = _es_dueno_o_staff(request, cuota.factura)
    if not autorizado:
        request.session['next_after_login'] = reverse('creditos_ventas:comprobante_cuota', args=[cuota.pk])
        messages.info(request, 'Inicia sesión para ver tu comprobante.')
        return redirect('storefront:customer_login')

    codigo = f'CV-{cuota.factura_id:05d}-{cuota.numero:02d}'
    total_cuotas = cuota.factura.cuotas.count()

    return render(request, 'creditos_ventas/comprobante_cuota.html', {
        'cuota': cuota, 'codigo': codigo, 'total_cuotas': total_cuotas,
        'puede_pagar_paypal': is_owner and cuota.estado == 'pendiente',
    })


def recibo_pago(request, pk):
    """Recibo único e imprimible de UN pago (cuota o total) registrado
    sobre una cuota. Se genera automáticamente después de cada pago,
    sea registrado por el staff o pagado por el cliente vía PayPal."""
    pago = get_object_or_404(
        PagoCuotaVenta.objects.select_related('cuota', 'cuota__factura', 'cuota__factura__customer'), pk=pk
    )
    autorizado, _ = _es_dueno_o_staff(request, pago.cuota.factura)
    if not autorizado:
        request.session['next_after_login'] = reverse('creditos_ventas:recibo_pago', args=[pago.pk])
        messages.info(request, 'Inicia sesión para ver tu recibo.')
        return redirect('storefront:customer_login')

    codigo = f'RP-{pago.cuota.factura_id:05d}-{pago.cuota.numero:02d}-{pago.pk:04d}'

    return render(request, 'creditos_ventas/recibo_pago.html', {
        'pago': pago, 'cuota': pago.cuota, 'codigo': codigo,
    })


def pagar_cuota_paypal(request, pk):
    """Página con el botón de PayPal para pagar el saldo completo de una
    cuota específica. Solo el cliente dueño de la factura puede entrar."""
    cuota = get_object_or_404(CuotaVenta.objects.select_related('factura', 'factura__customer'), pk=pk)
    _, is_owner = _es_dueno_o_staff(request, cuota.factura)

    if not is_owner:
        request.session['next_after_login'] = reverse('creditos_ventas:pagar_cuota_paypal', args=[cuota.pk])
        messages.info(request, 'Inicia sesión para pagar tu cuota.')
        return redirect('storefront:customer_login')

    if cuota.estado == 'pagada':
        messages.info(request, 'Esta cuota ya está pagada.')
        return redirect('creditos_ventas:comprobante_cuota', pk=cuota.pk)

    # Orden de pago: no se puede pagar esta cuota si hay cuotas anteriores pendientes
    prev_pending = CuotaVenta.objects.filter(
        factura=cuota.factura,
        numero__lt=cuota.numero,
        estado='pendiente',
    ).order_by('numero').first()
    if prev_pending:
        messages.error(
            request,
            f'Debes pagar la cuota {prev_pending.numero} antes de pagar la cuota {cuota.numero}.',
        )
        return redirect('storefront:my_cuotas')

    return render(request, 'creditos_ventas/pagar_cuota_paypal.html', {
        'cuota': cuota,
        'paypal_client_id': settings.PAYPAL_CLIENT_ID,
        'paypal_sdk_base': settings.PAYPAL_SDK_BASE,
    })


@require_POST
def paypal_create_order_cuota(request, pk):
    """Crea una orden en PayPal server-side por el saldo de la cuota."""
    cuota = get_object_or_404(CuotaVenta, pk=pk)
    _, is_owner = _es_dueno_o_staff(request, cuota.factura)
    if not is_owner:
        return JsonResponse({'error': 'No autorizado.'}, status=403)
    if cuota.estado == 'pagada':
        return JsonResponse({'error': 'Esta cuota ya está pagada.'}, status=400)

    # Orden de pago: verificar que no haya cuotas anteriores pendientes
    if CuotaVenta.objects.filter(factura=cuota.factura, numero__lt=cuota.numero, estado='pendiente').exists():
        return JsonResponse({'error': 'Debes pagar las cuotas anteriores primero.'}, status=400)

    # Leer el monto del cuerpo de la petición; si no viene, usar el saldo completo
    try:
        body = json.loads(request.body)
        amount = Decimal(str(body.get('amount', cuota.saldo))).quantize(Decimal('0.01'))
    except (json.JSONDecodeError, InvalidOperation, TypeError):
        return JsonResponse({'error': 'Monto inválido.'}, status=400)

    if amount <= 0 or amount > cuota.saldo:
        return JsonResponse({'error': f'El monto debe estar entre $0.01 y ${cuota.saldo}.'}, status=400)

    total = '{:.2f}'.format(amount)
    try:
        token = paypal_access_token()
        order = paypal_request(
            f'{settings.PAYPAL_API_BASE}/v2/checkout/orders',
            data=json.dumps({
                'intent': 'CAPTURE',
                'purchase_units': [{
                    'amount': {'currency_code': 'USD', 'value': total},
                    'description': f'Cuota {cuota.numero} - Factura #{cuota.factura_id}',
                }],
            }).encode(),
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
            },
        )
        return JsonResponse({'id': order['id']})
    except Exception as e:
        logger.exception('PayPal error (cuota %s): %s', cuota.pk, e)
        return JsonResponse({'error': 'No se pudo iniciar el pago. Intenta de nuevo.'}, status=502)


def paypal_capture_cuota(request, pk):
    """Captura el pago después de que PayPal lo aprueba y registra el
    abono sobre la cuota (por el saldo completo en el momento de crear
    la orden)."""
    cuota = get_object_or_404(CuotaVenta.objects.select_related('factura'), pk=pk)
    _, is_owner = _es_dueno_o_staff(request, cuota.factura)

    if request.method != 'POST':
        return redirect('creditos_ventas:pagar_cuota_paypal', pk=pk)
    if not is_owner:
        return JsonResponse({'error': 'No autorizado.'}, status=403)
    if cuota.estado == 'pagada':
        return JsonResponse({'error': 'Esta cuota ya está pagada.'}, status=400)

    try:
        order_id = json.loads(request.body).get('orderID')
        if not order_id:
            return JsonResponse({'error': 'Falta el identificador de la orden.'}, status=400)
        token = paypal_access_token()
        capture_data = paypal_request(
            f'{settings.PAYPAL_API_BASE}/v2/checkout/orders/{order_id}/capture',
            data=b'{}',
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
            },
        )
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Solicitud inválida.'}, status=400)
    except Exception as e:
        logger.exception('PayPal error (captura cuota %s): %s', cuota.pk, e)
        return JsonResponse({'error': 'No se pudo procesar el pago. Intenta de nuevo.'}, status=502)

    if capture_data.get('status') == 'COMPLETED':
        try:
            # Usar el monto real que PayPal capturó (puede ser parcial)
            captured_value = (
                capture_data['purchase_units'][0]['payments']['captures'][0]['amount']['value']
            )
            monto_capturado = Decimal(captured_value).quantize(Decimal('0.01'))
        except (KeyError, IndexError, InvalidOperation):
            logger.exception('No se pudo leer el monto capturado de PayPal para cuota %s', cuota.pk)
            return JsonResponse({'error': 'Error procesando la respuesta de PayPal.'}, status=502)

        try:
            pago = registrar_pago_cuota(
                cuota, monto_capturado, timezone.localdate(),
                observacion=f'Pago vía PayPal (orden {order_id})',
            )
        except ValueError as e:
            logger.exception('Error al registrar pago de cuota %s tras captura PayPal: %s', cuota.pk, e)
            return JsonResponse({'error': str(e)}, status=400)
        return JsonResponse({'status': 'ok', 'redirect': request.build_absolute_uri(
            reverse('creditos_ventas:recibo_pago', args=[pago.pk])
        )})

    return JsonResponse({'error': 'El pago no fue aprobado por PayPal.'}, status=400)


# ── Pago múltiple de cuotas (cliente elige una o varias en orden) ─────────────

def pagar_cuotas_multi_paypal(request, factura_pk):
    """Página para pagar una o más cuotas pendientes de una factura en un solo
    pago PayPal. El cliente elige cuáles con checkboxes; el orden se fuerza en
    JS (marcar la N marca automáticamente la 1..N-1)."""
    factura = get_object_or_404(Invoice.objects.select_related('customer'), pk=factura_pk)
    _, is_owner = _es_dueno_o_staff(request, factura)
    if not is_owner:
        request.session['next_after_login'] = reverse(
            'creditos_ventas:pagar_cuotas_multi_paypal', args=[factura_pk]
        )
        messages.info(request, 'Inicia sesión para pagar tus cuotas.')
        return redirect('storefront:customer_login')

    cuotas = list(CuotaVenta.objects.filter(factura=factura, estado='pendiente').order_by('numero'))
    if not cuotas:
        messages.info(request, 'No hay cuotas pendientes para esta factura.')
        return redirect('storefront:my_cuotas')

    return render(request, 'creditos_ventas/pagar_cuotas_multi_paypal.html', {
        'factura': factura,
        'cuotas': cuotas,
        'total_saldo': sum(c.saldo for c in cuotas),
        'today': timezone.localdate(),
        'paypal_client_id': settings.PAYPAL_CLIENT_ID,
        'paypal_sdk_base': settings.PAYPAL_SDK_BASE,
    })


@require_POST
def paypal_create_order_cuotas(request, factura_pk):
    """Crea una orden PayPal para el total de las cuotas seleccionadas."""
    factura = get_object_or_404(Invoice, pk=factura_pk)
    _, is_owner = _es_dueno_o_staff(request, factura)
    if not is_owner:
        return JsonResponse({'error': 'No autorizado.'}, status=403)

    try:
        body = json.loads(request.body)
        cuota_ids = [int(x) for x in body.get('cuota_ids', [])]
    except (json.JSONDecodeError, ValueError, TypeError):
        return JsonResponse({'error': 'Solicitud inválida.'}, status=400)

    if not cuota_ids:
        return JsonResponse({'error': 'Selecciona al menos una cuota.'}, status=400)

    cuotas = list(CuotaVenta.objects.filter(
        pk__in=cuota_ids, factura=factura, estado='pendiente',
    ).order_by('numero'))

    if not cuotas:
        return JsonResponse({'error': 'No hay cuotas válidas seleccionadas.'}, status=400)

    # La primera cuota seleccionada debe ser la primera pendiente de la factura
    primera_pendiente = CuotaVenta.objects.filter(
        factura=factura, estado='pendiente',
    ).order_by('numero').first()
    if cuotas[0].pk != primera_pendiente.pk:
        return JsonResponse({'error': 'Debes incluir la primera cuota pendiente.'}, status=400)

    # Deben ser cuotas consecutivas (sin saltar ninguna)
    numeros = [c.numero for c in cuotas]
    if numeros != list(range(numeros[0], numeros[0] + len(numeros))):
        return JsonResponse({'error': 'Las cuotas deben ser consecutivas.'}, status=400)

    total = '{:.2f}'.format(sum(c.saldo for c in cuotas))
    try:
        token = paypal_access_token()
        order = paypal_request(
            f'{settings.PAYPAL_API_BASE}/v2/checkout/orders',
            data=json.dumps({
                'intent': 'CAPTURE',
                'purchase_units': [{
                    'amount': {'currency_code': 'USD', 'value': total},
                    'description': f'{len(cuotas)} cuota(s) - Factura #{factura_pk}',
                }],
            }).encode(),
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
            },
        )
        return JsonResponse({'id': order['id']})
    except Exception as e:
        logger.exception('PayPal error (multi cuotas factura %s): %s', factura_pk, e)
        return JsonResponse({'error': 'No se pudo iniciar el pago. Intenta de nuevo.'}, status=502)


def paypal_capture_cuotas(request, factura_pk):
    """Captura el pago y distribuye el monto entre las cuotas seleccionadas."""
    if request.method != 'POST':
        return redirect('creditos_ventas:pagar_cuotas_multi_paypal', factura_pk=factura_pk)

    factura = get_object_or_404(Invoice.objects.select_related('customer'), pk=factura_pk)
    _, is_owner = _es_dueno_o_staff(request, factura)
    if not is_owner:
        return JsonResponse({'error': 'No autorizado.'}, status=403)

    try:
        body = json.loads(request.body)
        order_id = body.get('orderID')
        cuota_ids = [int(x) for x in body.get('cuota_ids', [])]
        if not order_id:
            return JsonResponse({'error': 'Falta el identificador de la orden.'}, status=400)
    except (json.JSONDecodeError, ValueError, TypeError):
        return JsonResponse({'error': 'Solicitud inválida.'}, status=400)

    cuotas = list(CuotaVenta.objects.filter(
        pk__in=cuota_ids, factura=factura, estado='pendiente',
    ).order_by('numero'))

    if not cuotas:
        return JsonResponse({'error': 'No hay cuotas válidas para registrar.'}, status=400)

    try:
        token = paypal_access_token()
        capture_data = paypal_request(
            f'{settings.PAYPAL_API_BASE}/v2/checkout/orders/{order_id}/capture',
            data=b'{}',
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
            },
        )
    except Exception as e:
        logger.exception('PayPal error (captura multi cuotas factura %s): %s', factura_pk, e)
        return JsonResponse({'error': 'No se pudo procesar el pago. Intenta de nuevo.'}, status=502)

    if capture_data.get('status') != 'COMPLETED':
        return JsonResponse({'error': 'El pago no fue aprobado por PayPal.'}, status=400)

    try:
        captured_value = capture_data['purchase_units'][0]['payments']['captures'][0]['amount']['value']
        restante = Decimal(captured_value).quantize(Decimal('0.01'))
    except (KeyError, IndexError, InvalidOperation):
        logger.exception('No se pudo leer el monto capturado para multi cuotas factura %s', factura_pk)
        return JsonResponse({'error': 'Error procesando la respuesta de PayPal.'}, status=502)

    ultimo_pago = None
    fecha = timezone.localdate()
    try:
        for cuota in cuotas:
            if restante <= 0:
                break
            monto_cuota = min(cuota.saldo, restante)
            ultimo_pago = registrar_pago_cuota(
                cuota, monto_cuota, fecha,
                observacion=f'Pago vía PayPal (orden {order_id})',
            )
            restante -= monto_cuota
    except ValueError as e:
        logger.exception('Error registrando pagos multi cuotas factura %s: %s', factura_pk, e)
        return JsonResponse({'error': str(e)}, status=400)

    redirect_url = request.build_absolute_uri(
        reverse('creditos_ventas:recibo_pago', args=[ultimo_pago.pk]) if ultimo_pago
        else reverse('storefront:my_cuotas')
    )
    return JsonResponse({'status': 'ok', 'redirect': redirect_url})


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
            pago = registrar_pago_cuota(
                cuota,
                form.cleaned_data['valor'],
                form.cleaned_data['fecha'],
                form.cleaned_data.get('observacion', ''),
            )
            messages.success(
                request,
                f'Pago registrado. Saldo restante de la cuota: ${cuota.saldo}'
            )
            return redirect('creditos_ventas:recibo_pago', pk=pago.pk)
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
