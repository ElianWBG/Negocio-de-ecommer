import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from billing.models import Customer, Invoice
from .models import CuotaVenta, PayPalCuotaOrder
from .services import generar_cuotas, registrar_pago_cuota


def _make_factura(total, estado='pendiente'):
    customer = Customer.objects.create(dni='1710034065', first_name='Ana', last_name='Pérez')
    return Invoice.objects.create(
        customer=customer, tipo_pago='credito',
        subtotal=total, tax=Decimal('0.00'), total=total,
        saldo=total, estado=estado,
    )


class GenerarCuotasTestCase(TestCase):
    def test_reparte_el_total_exacto_entre_las_cuotas(self):
        factura = _make_factura(Decimal('100.00'))
        generar_cuotas(factura, 3)

        cuotas = list(factura.cuotas.order_by('numero'))
        self.assertEqual(len(cuotas), 3)
        # 100 / 3 = 33.33, 33.33, 33.34 -> la suma debe cuadrar exacto
        self.assertEqual(sum(c.valor for c in cuotas), Decimal('100.00'))
        self.assertTrue(all(c.valor >= Decimal('0.01') for c in cuotas))

    def test_no_genera_cuotas_para_factura_anulada(self):
        factura = _make_factura(Decimal('100.00'), estado='anulada')
        with self.assertRaises(ValueError):
            generar_cuotas(factura, 3)
        self.assertEqual(factura.cuotas.count(), 0)

    def test_no_genera_cuotas_para_factura_de_contado(self):
        factura = _make_factura(Decimal('100.00'))
        factura.tipo_pago = 'contado'
        factura.save()
        with self.assertRaises(ValueError):
            generar_cuotas(factura, 3)

    def test_no_genera_cuotas_dos_veces(self):
        factura = _make_factura(Decimal('100.00'))
        generar_cuotas(factura, 2)
        with self.assertRaises(ValueError):
            generar_cuotas(factura, 2)

    def test_total_muy_bajo_para_el_numero_de_cuotas(self):
        factura = _make_factura(Decimal('0.02'))
        with self.assertRaises(ValueError):
            generar_cuotas(factura, 5)


class RegistrarPagoCuotaTestCase(TestCase):
    def setUp(self):
        self.factura = _make_factura(Decimal('90.00'))
        generar_cuotas(self.factura, 3)
        self.cuota1, self.cuota2, self.cuota3 = self.factura.cuotas.order_by('numero')

    def test_pago_parcial_no_marca_pagada(self):
        registrar_pago_cuota(self.cuota1, Decimal('10.00'), timezone.localdate())
        self.cuota1.refresh_from_db()
        self.assertEqual(self.cuota1.saldo, Decimal('20.00'))
        self.assertEqual(self.cuota1.estado, 'pendiente')

    def test_pago_completo_marca_cuota_pagada_y_actualiza_factura(self):
        registrar_pago_cuota(self.cuota1, self.cuota1.saldo, timezone.localdate())
        self.cuota1.refresh_from_db()
        self.factura.refresh_from_db()
        self.assertEqual(self.cuota1.estado, 'pagada')
        self.assertEqual(self.factura.estado, 'parcial')

    def test_pagar_todas_las_cuotas_marca_factura_pagada(self):
        for cuota in (self.cuota1, self.cuota2, self.cuota3):
            registrar_pago_cuota(cuota, cuota.saldo, timezone.localdate())
        self.factura.refresh_from_db()
        self.assertEqual(self.factura.estado, 'pagada')
        self.assertEqual(self.factura.saldo, Decimal('0.00'))

    def test_no_permite_pago_mayor_al_saldo_de_la_cuota(self):
        with self.assertRaises(ValueError):
            registrar_pago_cuota(self.cuota1, self.cuota1.saldo + 1, timezone.localdate())

    def test_no_permite_pago_negativo_ni_cero(self):
        for monto in (Decimal('0'), Decimal('-5')):
            with self.assertRaises(ValueError):
                registrar_pago_cuota(self.cuota1, monto, timezone.localdate())

    def test_no_permite_pagar_cuota_ya_pagada(self):
        registrar_pago_cuota(self.cuota1, self.cuota1.saldo, timezone.localdate())
        self.cuota1.refresh_from_db()
        with self.assertRaises(ValueError):
            registrar_pago_cuota(self.cuota1, Decimal('1.00'), timezone.localdate())


class PaypalCapturaCuotasTodoONadaTestCase(TestCase):
    """El endpoint de captura multi-cuota debe aplicar el pago a TODAS las
    cuotas de la orden o a NINGUNA: si una falla a mitad del lote, las que
    ya se habían aplicado en ese mismo request deben revertirse."""

    def setUp(self):
        self.factura = _make_factura(Decimal('60.00'))
        generar_cuotas(self.factura, 2)  # dos cuotas de $30
        self.cuota1, self.cuota2 = self.factura.cuotas.order_by('numero')

        self.user = User.objects.create_user(username='cliente', password='x')
        self.factura.customer.user = self.user
        self.factura.customer.save()
        self.client.force_login(self.user)

        self.orden = PayPalCuotaOrder.objects.create(
            order_id='ORDER123', factura=self.factura,
            cuota_ids=[self.cuota1.pk, self.cuota2.pk],
        )

    def _capture_url(self):
        return reverse('creditos_ventas:paypal_capture_cuotas', args=[self.factura.pk])

    @patch('creditos_ventas.views.paypal_access_token', return_value='fake-token')
    @patch('creditos_ventas.views.paypal_request')
    def test_captura_exitosa_paga_todas_las_cuotas(self, mock_request, mock_token):
        mock_request.return_value = {
            'status': 'COMPLETED',
            'purchase_units': [{'payments': {'captures': [{'amount': {'value': '60.00'}}]}}],
        }
        response = self.client.post(
            self._capture_url(), data=json.dumps({'orderID': 'ORDER123'}), content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ok')

        self.cuota1.refresh_from_db()
        self.cuota2.refresh_from_db()
        self.orden.refresh_from_db()
        self.assertEqual(self.cuota1.estado, 'pagada')
        self.assertEqual(self.cuota2.estado, 'pagada')
        self.assertTrue(self.orden.captured)

    @patch('creditos_ventas.views.paypal_access_token', return_value='fake-token')
    @patch('creditos_ventas.views.paypal_request')
    @patch('creditos_ventas.views.registrar_pago_cuota')
    def test_si_falla_una_cuota_se_revierte_todo_el_lote(self, mock_registrar, mock_request, mock_token):
        mock_request.return_value = {
            'status': 'COMPLETED',
            'purchase_units': [{'payments': {'captures': [{'amount': {'value': '60.00'}}]}}],
        }
        real_registrar = registrar_pago_cuota

        def fake_registrar(cuota, monto, fecha, observacion=''):
            if cuota.pk == self.cuota2.pk:
                raise ValueError('El saldo de la cuota cambió justo antes de aplicar el pago.')
            return real_registrar(cuota, monto, fecha, observacion=observacion)

        mock_registrar.side_effect = fake_registrar

        response = self.client.post(
            self._capture_url(), data=json.dumps({'orderID': 'ORDER123'}), content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

        self.cuota1.refresh_from_db()
        self.cuota2.refresh_from_db()
        self.orden.refresh_from_db()
        # Ni siquiera la primera cuota (que sí se procesó antes de fallar la
        # segunda) debe quedar aplicada: todo el lote va en una sola
        # transacción atómica.
        self.assertEqual(self.cuota1.estado, 'pendiente')
        self.assertEqual(self.cuota1.saldo, Decimal('30.00'))
        self.assertEqual(self.cuota2.estado, 'pendiente')
        self.assertFalse(self.orden.captured)

    def test_orden_ya_capturada_no_se_puede_reprocesar(self):
        self.orden.captured = True
        self.orden.save()
        response = self.client.post(
            self._capture_url(), data=json.dumps({'orderID': 'ORDER123'}), content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_cliente_ajeno_no_puede_capturar(self):
        otro = User.objects.create_user(username='otro', password='x')
        otro_customer = Customer.objects.create(dni='1700000001', first_name='Luis', last_name='Ruiz', user=otro)
        self.client.force_login(otro)
        response = self.client.post(
            self._capture_url(), data=json.dumps({'orderID': 'ORDER123'}), content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
