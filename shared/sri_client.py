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


def emitir_factura_sri(invoice) -> dict | None:
    """Envía la factura al microservicio SRI.

    Retorna el dict de respuesta del micro (con id, estado, clave_acceso…)
    o None si el micro no está configurado o la llamada falla.
    """
    base_url = getattr(settings, 'SRI_MICRO_URL', '').rstrip('/')
    if not base_url:
        return None

    api_key = getattr(settings, 'SRI_MICRO_API_KEY', '')

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
        'cliente_tipo_identificacion': '05',
        'cliente_razon_social': customer.full_name,
        'cliente_email': customer.email or '',
        'cliente_direccion': getattr(customer, 'address', '') or '',
        'cliente_telefono': getattr(customer, 'phone', '') or '',
        'items': items,
    }

    try:
        req = urllib.request.Request(
            f'{base_url}/api/v1/facturas/',
            data=json.dumps(payload).encode(),
            headers={
                'Content-Type': 'application/json',
                'X-Api-Key': api_key,
            },
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
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
