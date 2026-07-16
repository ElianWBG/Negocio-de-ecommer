"""Cliente HTTP mínimo para el microservicio de facturación SRI.

Llama a POST /api/v1/facturas/ y devuelve el dict de respuesta (202)
o None si el micro no está configurado o hay un error de red.
El envío es fire-and-forget: si falla, la factura ya fue creada en el
proyecto principal y el error queda logueado sin interrumpir al usuario.
"""
import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)


def emitir_factura_sri(invoice, purchase_request=None) -> dict | None:
    """Envía la factura al microservicio SRI.

    Retorna el dict de respuesta del micro (con id, estado, clave_acceso…)
    o None si el micro no está configurado o la llamada falla.
    El micro también se encarga de enviar el correo al cliente.
    """
    base_url = getattr(settings, 'SRI_MICRO_URL', '').rstrip('/')
    if not base_url:
        return None

    api_key = getattr(settings, 'SRI_MICRO_API_KEY', '')

    # Contexto de tienda para que el micro pueda armar el email con el diseño correcto
    from billing.models import ConfigNegocio
    config = ConfigNegocio.objects.first()
    store_name = (config.nombre_tienda if config else None) or 'nuestra tienda'
    logo_url = ''
    if config and getattr(config, 'logo', None):
        try:
            logo_url = config.logo.url
        except Exception:
            pass

    tipo_pago_label = {
        'contado': 'EFECTIVO / TRANSFERENCIA',
        'credito': 'CRÉDITO (CUOTAS)',
        'paypal': 'PAYPAL',
    }.get(invoice.tipo_pago, (invoice.tipo_pago or '').upper())

    items = [
        {
            'codigo': str(d.product.pk),
            'descripcion': d.product.name,
            'cantidad': str(d.quantity),
            'precio_unitario': str(d.unit_price),
            'descuento': '0',
            'codigo_iva': '2',
        }
        for d in invoice.details.select_related('product').all()
    ]

    customer = invoice.customer
    payload = {
        'cliente_identificacion': customer.dni or '9999999999',
        'cliente_tipo_identificacion': '04' if len(customer.dni or '') == 13 else ('06' if (customer.dni and not customer.dni.isdigit()) else '05'),
        'cliente_razon_social': customer.full_name,
        'cliente_email': customer.email or '',
        'cliente_direccion': getattr(customer, 'address', '') or '',
        'cliente_telefono': getattr(customer, 'phone', '') or '',
        'items': items,
        'store_name': store_name,
        'logo_url': logo_url,
        'tipo_pago_label': tipo_pago_label,
        'pedido_id': purchase_request.id if purchase_request else None,
        'factura_id_principal': invoice.pk,
    }

    try:
        req = urllib.request.Request(
            f'{base_url}/api/v1/facturas/',
            data=json.dumps(payload).encode(),
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}',
            },
            method='POST',
        )
        timeout = getattr(settings, 'SRI_MICRO_TIMEOUT', 30)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read())
            logger.info(
                'Factura %s enviada al micro SRI → id=%s estado=%s',
                invoice.pk, result.get('id'), result.get('estado'),
            )
            return result
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors='replace')
        logger.exception(
            'Error HTTP %s del micro SRI para factura %s: %s', e.code, invoice.pk, body
        )
    except Exception as e:
        logger.exception(
            'Error llamando al micro SRI para factura %s: %s', invoice.pk, e
        )
    return None
