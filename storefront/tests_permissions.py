from decimal import Decimal

from django.contrib.auth.models import User, Permission
from django.test import TestCase
from django.urls import reverse

from billing.models import Brand, Customer, Product, ProductGroup
from .models import PurchaseRequest, PurchaseRequestDetail


def _make_product():
    brand = Brand.objects.create(name='Marca X')
    group = ProductGroup.objects.create(name='Celulares')
    return Product.objects.create(
        name='Teléfono X', brand=brand, group=group,
        unit_price=Decimal('100.00'), stock=5,
    )


def _make_customer(username, dni):
    user = User.objects.create_user(username=username, password='x')
    return Customer.objects.create(
        dni=dni, first_name='Cliente', last_name=username, user=user,
    ), user


class PurchaseRequestPanelPermissionTestCase(TestCase):
    """Regresión de la escalada de privilegios corregida en el panel de
    solicitudes: solo un usuario con 'storefront.change_purchaserequest'
    (o superusuario) puede confirmar/rechazar pedidos."""

    @classmethod
    def setUpTestData(cls):
        cls.product = _make_product()
        cls.customer, cls.customer_user = _make_customer('cliente1', '1710034065')

        cls.purchase_request = PurchaseRequest.objects.create(customer=cls.customer)
        PurchaseRequestDetail.objects.create(
            request=cls.purchase_request, product=cls.product, quantity=1, unit_price=cls.product.unit_price,
        )

        cls.staff_user = User.objects.create_user(username='vendedor', password='x', is_staff=True)
        cls.staff_user.user_permissions.add(
            Permission.objects.get(codename='change_purchaserequest'),
            Permission.objects.get(codename='view_purchaserequest'),
        )

    def test_cliente_sin_permiso_no_puede_ver_el_listado_de_solicitudes(self):
        self.client.force_login(self.customer_user)
        response = self.client.get(reverse('storefront:purchase_request_list'))
        self.assertEqual(response.status_code, 302)

    def test_cliente_sin_permiso_no_puede_confirmar_una_solicitud(self):
        self.client.force_login(self.customer_user)
        response = self.client.post(
            reverse('storefront:purchase_request_confirm', args=[self.purchase_request.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.purchase_request.refresh_from_db()
        self.assertEqual(self.purchase_request.status, 'pendiente')

    def test_cliente_sin_permiso_no_puede_rechazar_una_solicitud(self):
        self.client.force_login(self.customer_user)
        response = self.client.post(
            reverse('storefront:purchase_request_reject', args=[self.purchase_request.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.purchase_request.refresh_from_db()
        self.assertEqual(self.purchase_request.status, 'pendiente')

    def test_anonimo_no_puede_confirmar_una_solicitud(self):
        response = self.client.post(
            reverse('storefront:purchase_request_confirm', args=[self.purchase_request.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.purchase_request.refresh_from_db()
        self.assertEqual(self.purchase_request.status, 'pendiente')

    def test_staff_con_permiso_puede_confirmar_y_genera_factura(self):
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse('storefront:purchase_request_confirm', args=[self.purchase_request.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.purchase_request.refresh_from_db()
        self.assertEqual(self.purchase_request.status, 'confirmada')
        self.assertIsNotNone(self.purchase_request.invoice)


class RequestSuccessIDORTestCase(TestCase):
    """Un cliente no debe poder ver la página de agradecimiento (con datos
    de contacto y links de WhatsApp) de un pedido ajeno adivinando el PK."""

    @classmethod
    def setUpTestData(cls):
        cls.product = _make_product()
        cls.owner, cls.owner_user = _make_customer('dueno', '1710034065')
        cls.stranger, cls.stranger_user = _make_customer('ajeno', '1700000001')
        cls.purchase_request = PurchaseRequest.objects.create(customer=cls.owner)

    def test_dueno_puede_ver_su_pagina_de_confirmacion(self):
        self.client.force_login(self.owner_user)
        response = self.client.get(reverse('storefront:request_success', args=[self.purchase_request.pk]))
        self.assertEqual(response.status_code, 200)

    def test_otro_cliente_no_puede_ver_pedido_ajeno(self):
        self.client.force_login(self.stranger_user)
        response = self.client.get(reverse('storefront:request_success', args=[self.purchase_request.pk]))
        self.assertEqual(response.status_code, 404)

    def test_anonimo_no_puede_ver_pedido_ajeno(self):
        response = self.client.get(reverse('storefront:request_success', args=[self.purchase_request.pk]))
        self.assertEqual(response.status_code, 404)
