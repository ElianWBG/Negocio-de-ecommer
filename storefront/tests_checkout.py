from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from billing.models import Brand, ProductGroup, Product, Customer, Invoice
from storefront.models import PurchaseRequest, PurchaseRequestDetail
from storefront.services import confirm_purchase_request, InsufficientStockError


def _make_product(stock, price='100.00', name='Prod'):
    brand = Brand.objects.create(name=f'Marca {name}')
    group = ProductGroup.objects.create(name=f'Grupo {name}')
    return Product.objects.create(
        name=name, brand=brand, group=group, unit_price=Decimal(price), stock=stock,
    )


def _make_customer(dni='1710034065'):
    # Sin email a propósito: así confirm_purchase_request no intenta armar el
    # PDF/XML ni enviar correo de confirmación (queda fuera del alcance del test).
    user = User.objects.create_user(username=f'cli{dni}', password='x')
    return Customer.objects.create(dni=dni, first_name='Cliente', last_name='Test', user=user)


def _pending_request(customer, product, quantity):
    pr = PurchaseRequest.objects.create(customer=customer)
    PurchaseRequestDetail.objects.create(
        request=pr, product=product, quantity=quantity, unit_price=product.unit_price,
    )
    return pr


class ConfirmPurchaseRequestTestCase(TestCase):
    """Cobertura del corazón del flujo de compra: confirm_purchase_request.
    Descuento de stock atómico, totales de la factura, rollback ante stock
    insuficiente e idempotencia frente a doble confirmación."""

    def test_confirmar_descuenta_stock_y_crea_factura_con_totales_correctos(self):
        customer = _make_customer()
        product = _make_product(stock=5, price='100.00')
        pr = _pending_request(customer, product, quantity=2)

        invoice = confirm_purchase_request(pr)

        product.refresh_from_db()
        pr.refresh_from_db()
        self.assertEqual(product.stock, 3)                 # 5 - 2
        self.assertEqual(pr.status, 'confirmada')
        self.assertEqual(pr.invoice_id, invoice.id)
        self.assertEqual(invoice.subtotal, Decimal('200.00'))
        self.assertEqual(invoice.tax, Decimal('30.00'))    # 15% de 200
        self.assertEqual(invoice.total, Decimal('230.00'))
        self.assertEqual(invoice.details.count(), 1)

    def test_stock_insuficiente_revierte_todo(self):
        customer = _make_customer()
        product = _make_product(stock=1, price='50.00')
        pr = _pending_request(customer, product, quantity=5)  # pide 5, hay 1

        with self.assertRaises(InsufficientStockError):
            confirm_purchase_request(pr)

        product.refresh_from_db()
        pr.refresh_from_db()
        self.assertEqual(product.stock, 1)          # stock intacto (rollback)
        self.assertEqual(pr.status, 'pendiente')    # sigue pendiente
        self.assertEqual(Invoice.objects.count(), 0)  # no se creó ninguna factura

    def test_confirmar_dos_veces_es_idempotente(self):
        customer = _make_customer()
        product = _make_product(stock=5, price='100.00')
        pr = _pending_request(customer, product, quantity=2)

        invoice1 = confirm_purchase_request(pr)
        invoice2 = confirm_purchase_request(pr)  # segunda confirmación del mismo pedido

        product.refresh_from_db()
        self.assertEqual(product.stock, 3)            # NO se descuenta dos veces
        self.assertEqual(invoice1.id, invoice2.id)    # devuelve la misma factura
        self.assertEqual(Invoice.objects.count(), 1)  # no se duplica la factura

    def test_multiples_lineas_descuentan_cada_producto(self):
        customer = _make_customer()
        p1 = _make_product(stock=10, price='20.00', name='A')
        p2 = _make_product(stock=4, price='5.00', name='B')
        pr = PurchaseRequest.objects.create(customer=customer)
        PurchaseRequestDetail.objects.create(request=pr, product=p1, quantity=3, unit_price=p1.unit_price)
        PurchaseRequestDetail.objects.create(request=pr, product=p2, quantity=4, unit_price=p2.unit_price)

        invoice = confirm_purchase_request(pr)

        p1.refresh_from_db()
        p2.refresh_from_db()
        self.assertEqual(p1.stock, 7)   # 10 - 3
        self.assertEqual(p2.stock, 0)   # 4 - 4
        self.assertEqual(invoice.subtotal, Decimal('80.00'))  # 3*20 + 4*5
