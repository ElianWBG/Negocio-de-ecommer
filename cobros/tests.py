from decimal import Decimal

from django.contrib.auth.models import User, Permission
from django.test import TestCase
from django.urls import reverse

from billing.models import Customer, Invoice
from .models import CobroFactura


class CobroFacturaBaseTestCase(TestCase):
    """Fixtures comunes: un usuario con permisos de cobros y una factura a
    crédito con saldo pendiente."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='cobrador', password='x')
        perms = Permission.objects.filter(
            codename__in=['view_cobrofactura', 'add_cobrofactura', 'change_cobrofactura', 'delete_cobrofactura']
        )
        cls.user.user_permissions.add(*perms)

        cls.customer = Customer.objects.create(dni='1710034065', first_name='Ana', last_name='Pérez')
        cls.factura = Invoice.objects.create(
            customer=cls.customer, tipo_pago='credito',
            subtotal=Decimal('100.00'), tax=Decimal('15.00'), total=Decimal('115.00'),
            saldo=Decimal('115.00'), estado='pendiente',
        )

    def setUp(self):
        self.client.force_login(self.user)


class CobroCreateViewTestCase(CobroFacturaBaseTestCase):
    def test_pago_valido_reduce_saldo_y_actualiza_estado(self):
        url = reverse('cobros:cobro_create', args=[self.factura.id])
        response = self.client.post(url, {'fecha': '2026-01-15', 'valor': '50.00', 'observacion': ''})
        self.assertEqual(response.status_code, 302)

        self.factura.refresh_from_db()
        self.assertEqual(self.factura.saldo, Decimal('65.00'))
        self.assertEqual(self.factura.estado, 'parcial')
        self.assertEqual(CobroFactura.objects.filter(factura=self.factura).count(), 1)

    def test_pago_que_completa_saldo_marca_factura_pagada(self):
        url = reverse('cobros:cobro_create', args=[self.factura.id])
        self.client.post(url, {'fecha': '2026-01-15', 'valor': '115.00', 'observacion': ''})

        self.factura.refresh_from_db()
        self.assertEqual(self.factura.saldo, Decimal('0.00'))
        self.assertEqual(self.factura.estado, 'pagada')

    def test_no_permite_sobrepago(self):
        """Un abono mayor al saldo debe rechazarse y no debe modificar la factura."""
        url = reverse('cobros:cobro_create', args=[self.factura.id])
        response = self.client.post(url, {'fecha': '2026-01-15', 'valor': '200.00', 'observacion': ''})
        self.assertEqual(response.status_code, 200)  # se re-renderiza el form con el error
        self.assertTrue(response.context['form'].errors)

        self.factura.refresh_from_db()
        self.assertEqual(self.factura.saldo, Decimal('115.00'))
        self.assertEqual(CobroFactura.objects.filter(factura=self.factura).count(), 0)

    def test_no_permite_pago_negativo_ni_cero(self):
        url = reverse('cobros:cobro_create', args=[self.factura.id])
        for valor in ('0', '-10'):
            response = self.client.post(url, {'fecha': '2026-01-15', 'valor': valor, 'observacion': ''})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['form'].errors)

        self.factura.refresh_from_db()
        self.assertEqual(self.factura.saldo, Decimal('115.00'))

    def test_no_permite_pago_sobre_factura_anulada(self):
        self.factura.estado = 'anulada'
        self.factura.save()

        url = reverse('cobros:cobro_create', args=[self.factura.id])
        response = self.client.post(url, {'fecha': '2026-01-15', 'valor': '10.00', 'observacion': ''})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CobroFactura.objects.filter(factura=self.factura).count(), 0)


class CobroUpdateDeleteTestCase(CobroFacturaBaseTestCase):
    def setUp(self):
        super().setUp()
        self.cobro = CobroFactura.objects.create(factura=self.factura, fecha='2026-01-10', valor=Decimal('40.00'))
        self.factura.saldo = Decimal('75.00')
        self.factura.estado = 'parcial'
        self.factura.save()

    def test_editar_pago_recalcula_saldo(self):
        url = reverse('cobros:cobro_update', args=[self.cobro.pk])
        response = self.client.post(url, {'fecha': '2026-01-10', 'valor': '60.00', 'observacion': ''})
        self.assertEqual(response.status_code, 302)

        self.factura.refresh_from_db()
        # Saldo antes de editar (75) + valor anterior (40) - valor nuevo (60) = 55
        self.assertEqual(self.factura.saldo, Decimal('55.00'))

    def test_editar_pago_no_puede_exceder_saldo_disponible(self):
        url = reverse('cobros:cobro_update', args=[self.cobro.pk])
        # saldo disponible = 75 + 40 = 115; pedir más que eso debe fallar
        response = self.client.post(url, {'fecha': '2026-01-10', 'valor': '200.00', 'observacion': ''})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)

        self.factura.refresh_from_db()
        self.assertEqual(self.factura.saldo, Decimal('75.00'))

    def test_eliminar_pago_repone_saldo(self):
        url = reverse('cobros:cobro_delete', args=[self.cobro.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

        self.factura.refresh_from_db()
        self.assertEqual(self.factura.saldo, Decimal('115.00'))
        self.assertEqual(self.factura.estado, 'pendiente')
        self.assertFalse(CobroFactura.objects.filter(pk=self.cobro.pk).exists())

    def test_no_puede_eliminar_pago_de_factura_anulada(self):
        self.factura.estado = 'anulada'
        self.factura.save()

        url = reverse('cobros:cobro_delete', args=[self.cobro.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(CobroFactura.objects.filter(pk=self.cobro.pk).exists())
