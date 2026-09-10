from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from billing.models import Customer


class HomeDashboardCustomerAccessTestCase(TestCase):
    """Regresión: una cuenta de cliente de la tienda (con customer_profile)
    no debe poder ver el dashboard del panel (ventas, ingresos, clientes)
    solo por estar logueada. billing:home es la única vista del panel que no
    exige un permiso puntual (es el destino de fallback cuando falta uno en
    cualquier otra), así que necesita su propio chequeo explícito."""

    def test_cliente_no_ve_el_dashboard(self):
        user = User.objects.create_user(username='cliente1', password='x')
        Customer.objects.create(dni='1710034065', first_name='Ana', last_name='Pérez', user=user)
        self.client.force_login(user)

        response = self.client.get(reverse('billing:home'))

        self.assertRedirects(response, reverse('storefront:catalog_list'))

    def test_staff_sin_permisos_puntuales_si_ve_el_dashboard(self):
        user = User.objects.create_user(username='staff1', password='x')
        self.client.force_login(user)

        response = self.client.get(reverse('billing:home'))

        self.assertEqual(response.status_code, 200)

    def test_superusuario_ve_el_dashboard(self):
        user = User.objects.create_superuser(username='root1', password='x', email='root1@x.com')
        self.client.force_login(user)

        response = self.client.get(reverse('billing:home'))

        self.assertEqual(response.status_code, 200)
