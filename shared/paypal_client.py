"""Cliente mínimo para la API REST de PayPal (checkout orders v2).

Extraído de storefront.views para poder reutilizarlo también desde
creditos_ventas (pago de una cuota específica), sin duplicar el código
de reintentos/autenticación.
"""
import base64
import json
import socket
import time
import urllib.error
import urllib.request

from django.conf import settings


def paypal_request(url, data, headers, timeout=None, attempts=None):
    """Hace un POST a PayPal y devuelve el JSON. Reintenta ante fallos
    transitorios (timeout, 5xx, red caída). Timeout y nº de intentos
    configurables por env (PAYPAL_TIMEOUT, PAYPAL_MAX_ATTEMPTS).
    Lanza Exception si falla todo."""
    if timeout is None:
        timeout = getattr(settings, 'PAYPAL_TIMEOUT', 20)
    if attempts is None:
        attempts = max(1, getattr(settings, 'PAYPAL_MAX_ATTEMPTS', 3))
    last_error = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors='replace')
            # 4xx (ej. pago rechazado) no se reintenta; 5xx sí.
            if e.code < 500:
                raise Exception(f'PayPal {e.code}: {body}')
            last_error = Exception(f'PayPal {e.code}: {body}')
        except (urllib.error.URLError, socket.timeout, TimeoutError) as e:
            last_error = e
        if attempt < attempts - 1:
            # Backoff exponencial: 0.5s, 1s, 2s...
            time.sleep(0.5 * (2 ** attempt))
    raise last_error


def paypal_access_token():
    """Obtiene un access token de la API de PayPal."""
    credentials = base64.b64encode(
        f'{settings.PAYPAL_CLIENT_ID}:{settings.PAYPAL_SECRET}'.encode()
    ).decode()
    data = paypal_request(
        f'{settings.PAYPAL_API_BASE}/v1/oauth2/token',
        data=b'grant_type=client_credentials',
        headers={
            'Authorization': f'Basic {credentials}',
            'Content-Type': 'application/x-www-form-urlencoded',
        },
    )
    return data['access_token']
