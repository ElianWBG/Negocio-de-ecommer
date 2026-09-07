import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from billing.models import Brand, ProductGroup, Product, Customer
from storefront.models import PurchaseRequest, PurchaseRequestDetail


def _setup_pending_request():
    """Cliente + pedido pendiente de 2 x $100 → subtotal 200, IVA 30, total 230.00."""
    brand = Brand.objects.create(name='Marca')
    group = ProductGroup.objects.create(name='Grupo')
    product = Product.objects.create(
        name='Producto', brand=brand, group=group, unit_price=Decimal('100.00'), stock=5,
    )
    user = User.objects.create_user(username='cliente_pago', password='x')
    customer = Customer.objects.create(dni='1710034065', first_name='C', last_name='P', user=user)
    pr = PurchaseRequest.objects.create(customer=customer)
    PurchaseRequestDetail.objects.create(request=pr, product=product, quantity=2, unit_price=product.unit_price)
    return user, pr  # total_estimado == 230.00 (23000 centavos)


class PayPalCaptureAmountTestCase(TestCase):
    """El monto capturado por PayPal debe coincidir con el total del pedido.
    Un monto distinto NO confirma el pedido."""

    def setUp(self):
        self.user, self.pr = _setup_pending_request()
        self.pr.paypal_order_id = 'ORDER1'
        self.pr.save(update_fields=['paypal_order_id'])
        self.client.force_login(self.user)
        self.url = reverse('storefront:paypal_capture', args=[self.pr.pk])

    def _capture(self):
        return self.client.post(self.url, data=json.dumps({'orderID': 'ORDER1'}), content_type='application/json')

    @patch('storefront.views.paypal_access_token', return_value='fake-token')
    @patch('storefront.views.paypal_request')
    def test_monto_incorrecto_no_confirma(self, mock_request, mock_token):
        mock_request.return_value = {
            'status': 'COMPLETED',
            'purchase_units': [{'payments': {'captures': [{'amount': {'value': '1.00'}}]}}],  # ¡solo $1!
        }
        response = self._capture()
        self.assertEqual(response.status_code, 400)
        self.pr.refresh_from_db()
        self.assertEqual(self.pr.status, 'pendiente')  # NO se confirmó

    @patch('storefront.views.paypal_access_token', return_value='fake-token')
    @patch('storefront.views.paypal_request')
    def test_monto_correcto_confirma(self, mock_request, mock_token):
        mock_request.return_value = {
            'status': 'COMPLETED',
            'purchase_units': [{'payments': {'captures': [{'amount': {'value': '230.00'}}]}}],
        }
        response = self._capture()
        self.assertEqual(response.status_code, 200)
        self.pr.refresh_from_db()
        self.assertEqual(self.pr.status, 'confirmada')


class PayPhoneAmountTestCase(TestCase):
    """El monto cobrado por PayPhone (en centavos) debe coincidir con el total.
    Un monto distinto NO confirma el pedido."""

    def setUp(self):
        self.user, self.pr = _setup_pending_request()
        self.pr.payphone_client_transaction_id = 'TX1'
        self.pr.save(update_fields=['payphone_client_transaction_id'])
        self.client.force_login(self.user)
        self.url = reverse('storefront:payphone_response')

    def _respond(self):
        return self.client.get(self.url, {'id': '999', 'clientTransactionId': 'TX1'})

    @patch('storefront.payphone.confirm_payment')
    def test_monto_incorrecto_no_confirma(self, mock_confirm):
        mock_confirm.return_value = {'statusCode': 3, 'transactionId': 12345, 'amount': 100}  # $1.00
        self._respond()
        self.pr.refresh_from_db()
        self.assertEqual(self.pr.status, 'pendiente')  # NO se confirmó

    @patch('storefront.payphone.confirm_payment')
    def test_monto_correcto_confirma(self, mock_confirm):
        mock_confirm.return_value = {'statusCode': 3, 'transactionId': 12345, 'amount': 23000}  # $230.00
        self._respond()
        self.pr.refresh_from_db()
        self.assertEqual(self.pr.status, 'confirmada')
