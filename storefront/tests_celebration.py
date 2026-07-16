from django.test import TestCase

from billing.models import Customer
from storefront.models import PurchaseRequest


class PurchaseCelebrationTests(TestCase):
    """Las páginas de éxito (PayPal y pedido) disparan la animación de
    'compra confirmada' — pantalla vibra + estallido de partículas + el
    ícono entra con rebote. Se prueba vía include compartido, no HTTP:
    ambas vistas exigen dueño autenticado y ese flujo ya lo cubren otros
    tests; aquí solo importa que el partial se incluya y sea válido."""

    @classmethod
    def setUpTestData(cls):
        cls.customer = Customer.objects.create(
            dni='0912345678', first_name='Ana', last_name='Pérez', email='ana@test.com',
        )
        cls.purchase_request = PurchaseRequest.objects.create(customer=cls.customer)

    def _render(self, template_name, extra_context=None):
        from django.template.loader import render_to_string
        context = {'purchase_request': self.purchase_request}
        if extra_context:
            context.update(extra_context)
        return render_to_string(template_name, context)

    def test_payment_success_includes_celebration(self):
        html = self._render('storefront/payment_success.html')
        self.assertIn('celebrate-badge-pop', html)
        self.assertIn('celebrate-shake', html)

    def test_request_success_includes_celebration(self):
        html = self._render('storefront/request_success.html', {'whatsapp_links': []})
        self.assertIn('celebrate-badge-pop', html)
        self.assertIn('celebrate-shake', html)

    def test_celebration_respects_reduced_motion(self):
        html = self._render('storefront/payment_success.html')
        self.assertIn('prefers-reduced-motion: reduce', html)
        self.assertIn('.celebrate-particle { display: none; }', html)

    def test_celebration_included_exactly_once(self):
        html = self._render('storefront/payment_success.html')
        # 'celebrate-overlay' aparece 2 veces a propósito (selector CSS + JS
        # que crea el nodo); lo que no debe duplicarse es el bloque en sí.
        self.assertEqual(html.count('@keyframes celebrate-particle-anim'), 1)
