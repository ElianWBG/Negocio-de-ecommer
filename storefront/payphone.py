"""Cliente delgado para la API de PayPhone (Botón de Pago por redirección).

Documentación oficial: https://docs.payphone.app/boton-de-pago

Flujo:
1. prepare_payment(...) -> POST /api/button/Prepare
   Devuelve una URL (payWithCard) a la que se redirige al cliente para
   que pague. Esa URL la sirve PayPhone directamente: nunca le pedimos
   al cliente sus datos de tarjeta en nuestro propio formulario.
2. PayPhone redirige de vuelta a nuestra responseUrl con ?id=...&clientTransactionId=...
3. confirm_payment(...) -> POST /api/button/V2/Confirm
   Verifica del lado del servidor (no confiamos en los parámetros de la
   URL por sí solos) si el pago realmente fue aprobado.
"""
import requests
from django.conf import settings

BASE_URL = 'https://pay.payphonetodoesposible.com/api'
TIMEOUT_SECONDS = 15

# Código de estado que PayPhone devuelve cuando el pago fue aprobado.
STATUS_APPROVED = 3


class PayphoneError(Exception):
    """Error de comunicación con PayPhone o respuesta inesperada."""
    pass


def _headers():
    return {
        'Authorization': f'Bearer {settings.PAYPHONE_TOKEN}',
        'Content-Type': 'application/json',
    }


def prepare_payment(*, amount_cents, client_transaction_id, reference, response_url, cancellation_url):
    """Inicia una transacción. `amount_cents` es el monto TOTAL a cobrar
    (con IVA incluido) en centavos, como entero — así lo exige PayPhone
    (ej: $10.50 -> 1050). Devuelve el dict de PayPhone con, entre otros,
    'payWithCard' (URL a la que redirigir al cliente)."""
    payload = {
        'amount': amount_cents,
        'amountWithoutTax': amount_cents,
        'clientTransactionId': client_transaction_id,
        'currency': 'USD',
        'storeId': settings.PAYPHONE_STORE_ID,
        'reference': reference,
        'responseUrl': response_url,
        'cancellationUrl': cancellation_url,
    }
    try:
        resp = requests.post(
            f'{BASE_URL}/button/Prepare', json=payload,
            headers=_headers(), timeout=TIMEOUT_SECONDS
        )
        data = resp.json()
    except (requests.RequestException, ValueError) as e:
        raise PayphoneError(f'No se pudo conectar con PayPhone: {e}')

    if resp.status_code != 200 or 'paymentId' not in data:
        raise PayphoneError(data.get('message', 'PayPhone rechazó la solicitud de pago.'))
    return data


def confirm_payment(*, transaction_id, client_transaction_id):
    """Verifica del lado del servidor el estado real de una transacción.
    Devuelve el dict de PayPhone con 'statusCode' (3 = aprobado) y el
    resto del detalle de la transacción."""
    payload = {'id': int(transaction_id), 'clientTxId': client_transaction_id}
    try:
        resp = requests.post(
            f'{BASE_URL}/button/V2/Confirm', json=payload,
            headers=_headers(), timeout=TIMEOUT_SECONDS
        )
        data = resp.json()
    except (requests.RequestException, ValueError) as e:
        raise PayphoneError(f'No se pudo conectar con PayPhone: {e}')

    if resp.status_code != 200 or 'statusCode' not in data:
        raise PayphoneError(data.get('message', 'No se pudo confirmar el pago con PayPhone.'))
    return data
