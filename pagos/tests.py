from decimal import Decimal

from django.contrib.auth.models import User, Permission
from django.test import TestCase
from django.urls import reverse

from billing.models import Supplier
from purchasing.models import Purchase
from .models import PagoCompra


class PagoCompraBaseTestCase(TestCase):
    """Fixtures comunes: un usuario con permisos de pagos y una compra a
    crédito con saldo pendiente."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='pagador', password='x')
        perms = Permission.objects.filter(
            codename__in=['view_pagocompra', 'add_pagocompra', 'change_pagocompra', 'delete_pagocompra']
        )
        cls.user.user_permissions.add(*perms)

        cls.supplier = Supplier.objects.create(name='Proveedor S.A.')
        cls.compra = Purchase.objects.create(
            supplier=cls.supplier, document_number='DOC-001', tipo_pago='credito',
            subtotal=Decimal('200.00'), tax=Decimal('30.00'), total=Decimal('230.00'),
            saldo=Decimal('230.00'), estado='pendiente',
        )

    def setUp(self):
        self.client.force_login(self.user)


class PagoCreateViewTestCase(PagoCompraBaseTestCase):
    def test_pago_valido_reduce_saldo_y_actualiza_estado(self):
        url = reverse('pagos:pago_create', args=[self.compra.id])
        response = self.client.post(url, {'fecha': '2026-01-15', 'valor': '100.00', 'observacion': ''})
        self.assertEqual(response.status_code, 302)

        self.compra.refresh_from_db()
        self.assertEqual(self.compra.saldo, Decimal('130.00'))
        self.assertEqual(self.compra.estado, 'parcial')
        self.assertEqual(PagoCompra.objects.filter(compra=self.compra).count(), 1)

    def test_pago_que_completa_saldo_marca_compra_pagada(self):
        url = reverse('pagos:pago_create', args=[self.compra.id])
        self.client.post(url, {'fecha': '2026-01-15', 'valor': '230.00', 'observacion': ''})

        self.compra.refresh_from_db()
        self.assertEqual(self.compra.saldo, Decimal('0.00'))
        self.assertEqual(self.compra.estado, 'pagada')

    def test_no_permite_sobrepago(self):
        url = reverse('pagos:pago_create', args=[self.compra.id])
        response = self.client.post(url, {'fecha': '2026-01-15', 'valor': '500.00', 'observacion': ''})
        self.assertEqual(response.status_code, 200)  # se re-renderiza el form con el error
        self.assertTrue(response.context['form'].errors)

        self.compra.refresh_from_db()
        self.assertEqual(self.compra.saldo, Decimal('230.00'))
        self.assertEqual(PagoCompra.objects.filter(compra=self.compra).count(), 0)

    def test_no_permite_pago_negativo_ni_cero(self):
        url = reverse('pagos:pago_create', args=[self.compra.id])
        for valor in ('0', '-10'):
            response = self.client.post(url, {'fecha': '2026-01-15', 'valor': valor, 'observacion': ''})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['form'].errors)

        self.compra.refresh_from_db()
        self.assertEqual(self.compra.saldo, Decimal('230.00'))

    def test_no_permite_pago_sobre_compra_anulada(self):
        self.compra.estado = 'anulada'
        self.compra.save()

        url = reverse('pagos:pago_create', args=[self.compra.id])
        response = self.client.post(url, {'fecha': '2026-01-15', 'valor': '10.00', 'observacion': ''})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(PagoCompra.objects.filter(compra=self.compra).count(), 0)


class PagoUpdateDeleteTestCase(PagoCompraBaseTestCase):
    def setUp(self):
        super().setUp()
        self.pago = PagoCompra.objects.create(compra=self.compra, fecha='2026-01-10', valor=Decimal('80.00'))
        self.compra.saldo = Decimal('150.00')
        self.compra.estado = 'parcial'
        self.compra.save()

    def test_editar_pago_recalcula_saldo(self):
        url = reverse('pagos:pago_update', args=[self.pago.pk])
        response = self.client.post(url, {'fecha': '2026-01-10', 'valor': '100.00', 'observacion': ''})
        self.assertEqual(response.status_code, 302)

        self.compra.refresh_from_db()
        # Saldo antes de editar (150) + valor anterior (80) - valor nuevo (100) = 130
        self.assertEqual(self.compra.saldo, Decimal('130.00'))

    def test_editar_pago_no_puede_exceder_saldo_disponible(self):
        url = reverse('pagos:pago_update', args=[self.pago.pk])
        # saldo disponible = 150 + 80 = 230; pedir más que eso debe fallar
        response = self.client.post(url, {'fecha': '2026-01-10', 'valor': '500.00', 'observacion': ''})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)

        self.compra.refresh_from_db()
        self.assertEqual(self.compra.saldo, Decimal('150.00'))

    def test_eliminar_pago_repone_saldo(self):
        url = reverse('pagos:pago_delete', args=[self.pago.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

        self.compra.refresh_from_db()
        self.assertEqual(self.compra.saldo, Decimal('230.00'))
        self.assertEqual(self.compra.estado, 'pendiente')
        self.assertFalse(PagoCompra.objects.filter(pk=self.pago.pk).exists())

    def test_no_puede_eliminar_pago_de_compra_anulada(self):
        self.compra.estado = 'anulada'
        self.compra.save()

        url = reverse('pagos:pago_delete', args=[self.pago.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(PagoCompra.objects.filter(pk=self.pago.pk).exists())
