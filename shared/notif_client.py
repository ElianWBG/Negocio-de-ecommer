"""Cliente HTTP para el microservicio de notificaciones.

Llama a POST /api/v1/enviar/ y devuelve el dict de respuesta o None si
el micro no está configurado o falla.  Fire-and-forget: el error queda
logueado sin interrumpir el flujo principal.

Variables de entorno requeridas (en Railway/local):
    NOTIF_MICRO_URL     URL base del microservicio, p.ej. https://notif.up.railway.app
    NOTIF_MICRO_API_KEY API key generada en el admin del micro (modelo Cliente)

Eventos soportados:
    bienvenida          → email al cliente nuevo
    pedido_nuevo        → email + WhatsApp al proveedor
    pedido_confirmado   → email al cliente
    cuota_vencida       → email al cliente con cuota vencida
    stock_bajo          → email + WhatsApp al proveedor
"""
import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)


def _enviar(evento: str, email: str = '', telefono: str = '', contexto: dict | None = None) -> dict | None:
    base_url = getattr(settings, 'NOTIF_MICRO_URL', '').rstrip('/')
    if not base_url:
        return None

    api_key = getattr(settings, 'NOTIF_MICRO_API_KEY', '')
    payload = json.dumps({
        'evento': evento,
        'email': email,
        'telefono': telefono,
        'contexto': contexto or {},
    }).encode()

    req = urllib.request.Request(
        f'{base_url}/api/v1/enviar/',
        data=payload,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
        },
        method='POST',
    )
    timeout = getattr(settings, 'NOTIF_MICRO_TIMEOUT', 10)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read())
            logger.info(
                'Notif micro [%s] enviados=%s fallidos=%s',
                evento, result.get('enviados'), result.get('fallidos'),
            )
            return result
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors='replace')
        logger.error('Error HTTP %s del micro de notificaciones para [%s]: %s', e.code, evento, body[:300])
    except Exception as e:
        logger.error('Error llamando al micro de notificaciones para [%s]: %s', evento, e)
    return None


# ── Helpers por evento ────────────────────────────────────────────────

def notificar_bienvenida(user, store_name: str, login_url: str, color: str = '#B5441B'):
    return _enviar(
        evento='bienvenida',
        email=user.email,
        contexto={
            'nombre_cliente': user.first_name or user.email,
            'store_name': store_name,
            'login_url': login_url,
            'color_primario': color,
        },
    )


def notificar_pedido_nuevo(email_admin: str, telefono_admin: str, purchase_request, panel_url: str, store_name: str):
    items_text = '\n'.join(
        f'  - {d.product.name} x{d.quantity} = ${d.subtotal}'
        for d in purchase_request.details.select_related('product').all()
    )
    return _enviar(
        evento='pedido_nuevo',
        email=email_admin,
        telefono=telefono_admin,
        contexto={
            'pedido_id': purchase_request.id,
            'nombre_cliente': purchase_request.customer.full_name,
            'email_cliente': purchase_request.customer.email or '',
            'telefono_cliente': getattr(purchase_request.customer, 'phone', '') or '',
            'total': str(purchase_request.total_estimado),
            'items_text': items_text,
            'panel_url': panel_url,
            'store_name': store_name,
        },
    )


def notificar_pedido_confirmado(invoice, purchase_request, store_name: str, color: str = '#B5441B'):
    from django.utils import timezone
    customer = invoice.customer
    if not customer.email:
        return None
    items = [
        {
            'nombre': d.product.name,
            'cantidad': d.quantity,
            'subtotal': f'{d.subtotal:.2f}',
        }
        for d in invoice.details.select_related('product').all()
    ]
    return _enviar(
        evento='pedido_confirmado',
        email=customer.email,
        contexto={
            'nombre_cliente': customer.full_name,
            'pedido_id': purchase_request.id,
            'total': f'{invoice.total:.2f}',
            'items': items,
            'store_name': store_name,
            'color_primario': color,
            'fecha': invoice.invoice_date.strftime('%d/%m/%Y') if invoice.invoice_date else '',
        },
    )


def notificar_cuota_vencida(cuota, store_name: str):
    customer = cuota.factura.customer
    if not customer.email:
        return None
    return _enviar(
        evento='cuota_vencida',
        email=customer.email,
        contexto={
            'nombre_cliente': customer.first_name or customer.full_name,
            'factura_id': cuota.factura_id,
            'cuota_numero': cuota.numero,
            'valor': f'{cuota.saldo:.2f}',
            'fecha_vencimiento': cuota.fecha_vencimiento.strftime('%d/%m/%Y'),
            'store_name': store_name,
        },
    )


def notificar_stock_bajo(product, threshold: int, panel_url: str, email_admin: str, store_name: str):
    return _enviar(
        evento='stock_bajo',
        email=email_admin,
        contexto={
            'nombre_producto': product.name,
            'stock': product.stock,
            'threshold': threshold,
            'panel_url': panel_url,
            'store_name': store_name,
        },
    )
