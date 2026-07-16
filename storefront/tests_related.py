from django.test import TestCase
from django.urls import reverse

from billing.models import Brand, Product, ProductGroup


class RelatedProductsTests(TestCase):
    """La ficha de producto muestra 'Productos relacionados' debajo de las
    reseñas: mismo grupo primero, completando con la misma marca si faltan."""

    @classmethod
    def setUpTestData(cls):
        cls.brand = Brand.objects.create(name='Samsung')
        cls.other_brand = Brand.objects.create(name='Apple')
        cls.group = ProductGroup.objects.create(name='Celulares')
        cls.other_group = ProductGroup.objects.create(name='Accesorios')

        cls.main = Product.objects.create(
            name='Galaxy S26 Ultra', brand=cls.brand, group=cls.group,
            unit_price='2000.00', stock=290, is_active=True,
        )
        cls.same_group = Product.objects.create(
            name='Galaxy S26', brand=cls.brand, group=cls.group,
            unit_price='1500.00', stock=10, is_active=True,
        )
        cls.same_brand_other_group = Product.objects.create(
            name='Cargador Samsung 45W', brand=cls.brand, group=cls.other_group,
            unit_price='30.00', stock=50, is_active=True,
        )
        cls.inactive_same_group = Product.objects.create(
            name='Galaxy S25 (descontinuado)', brand=cls.brand, group=cls.group,
            unit_price='1200.00', stock=0, is_active=False,
        )
        cls.unrelated = Product.objects.create(
            name='iPhone 17', brand=cls.other_brand, group=cls.other_group,
            unit_price='1800.00', stock=20, is_active=True,
        )

    def test_related_products_in_context(self):
        response = self.client.get(reverse('storefront:product_detail', args=[self.main.pk]))
        self.assertEqual(response.status_code, 200)
        related_ids = {p.pk for p in response.context['related']}

        self.assertNotIn(self.main.pk, related_ids)          # nunca se recomienda a sí mismo
        self.assertNotIn(self.inactive_same_group.pk, related_ids)  # inactivo, fuera
        self.assertIn(self.same_group.pk, related_ids)        # mismo grupo
        self.assertIn(self.same_brand_other_group.pk, related_ids)  # misma marca, completa el cupo
        self.assertNotIn(self.unrelated.pk, related_ids)      # ni grupo ni marca en común

    def test_related_section_renders_in_html(self):
        response = self.client.get(reverse('storefront:product_detail', args=[self.main.pk]))
        html = response.content.decode()
        self.assertIn('Productos relacionados', html)
        self.assertIn(self.same_group.name, html)

    def test_no_related_section_without_matches(self):
        lonely_group = ProductGroup.objects.create(name='Únicos')
        lonely_brand = Brand.objects.create(name='Marca Única')
        lonely = Product.objects.create(
            name='Producto solitario', brand=lonely_brand, group=lonely_group,
            unit_price='10.00', stock=5, is_active=True,
        )
        response = self.client.get(reverse('storefront:product_detail', args=[lonely.pk]))
        self.assertNotIn('<div class="related-section">', response.content.decode())
