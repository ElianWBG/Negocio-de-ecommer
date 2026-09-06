from decimal import Decimal

from django.test import TestCase

from billing.models import Brand, ProductGroup, Product
from purchasing.forms import PurchaseDetailForm


def _make_product():
    brand = Brand.objects.create(name='Marca')
    group = ProductGroup.objects.create(name='Grupo')
    return Product.objects.create(
        name='Producto', brand=brand, group=group,
        unit_price=Decimal('10.00'), stock=5,
    )


class PurchaseDetailFormValidationTestCase(TestCase):
    """Regresión de la validación de servidor en las líneas de compra:
    cantidad >= 1 y costo unitario >= 0, aunque el POST salte los `min` del HTML."""

    def setUp(self):
        self.product = _make_product()

    def _form(self, quantity, unit_cost):
        return PurchaseDetailForm(data={
            'product': self.product.pk, 'quantity': quantity, 'unit_cost': unit_cost,
        })

    def test_rechaza_cantidad_cero(self):
        form = self._form(0, '5.00')
        self.assertFalse(form.is_valid())
        self.assertIn('quantity', form.errors)

    def test_rechaza_costo_negativo(self):
        form = self._form(2, '-5.00')
        self.assertFalse(form.is_valid())
        self.assertIn('unit_cost', form.errors)

    def test_acepta_linea_valida(self):
        form = self._form(2, '5.00')
        self.assertTrue(form.is_valid(), form.errors)

    def test_acepta_costo_cero_muestra_gratis(self):
        # Un producto de muestra/gratis (costo 0) es válido: solo se rechaza el negativo.
        form = self._form(1, '0')
        self.assertTrue(form.is_valid(), form.errors)
