from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from billing.models import Supplier
from purchasing.models import Purchase
from .services import generar_cuotas, registrar_pago_cuota


def _make_compra(total, estado='pendiente'):
    supplier = Supplier.objects.create(name='Proveedor S.A.')
    return Purchase.objects.create(
        supplier=supplier, document_number='DOC-001', tipo_pago='credito',
        subtotal=total, tax=Decimal('0.00'), total=total,
        saldo=total, estado=estado,
    )


class GenerarCuotasTestCase(TestCase):
    def test_reparte_el_total_exacto_entre_las_cuotas(self):
        compra = _make_compra(Decimal('100.00'))
        generar_cuotas(compra, 3)

        cuotas = list(compra.cuotas.order_by('numero'))
        self.assertEqual(len(cuotas), 3)
        self.assertEqual(sum(c.valor for c in cuotas), Decimal('100.00'))
        self.assertTrue(all(c.valor >= Decimal('0.01') for c in cuotas))

    def test_no_genera_cuotas_para_compra_anulada(self):
        compra = _make_compra(Decimal('100.00'), estado='anulada')
        with self.assertRaises(ValueError):
            generar_cuotas(compra, 3)

    def test_no_genera_cuotas_para_compra_de_contado(self):
        compra = _make_compra(Decimal('100.00'))
        compra.tipo_pago = 'contado'
        compra.save()
        with self.assertRaises(ValueError):
            generar_cuotas(compra, 3)

    def test_no_genera_cuotas_dos_veces(self):
        compra = _make_compra(Decimal('100.00'))
        generar_cuotas(compra, 2)
        with self.assertRaises(ValueError):
            generar_cuotas(compra, 2)

    def test_total_muy_bajo_para_el_numero_de_cuotas(self):
        compra = _make_compra(Decimal('0.02'))
        with self.assertRaises(ValueError):
            generar_cuotas(compra, 5)


class RegistrarPagoCuotaTestCase(TestCase):
    def setUp(self):
        self.compra = _make_compra(Decimal('90.00'))
        generar_cuotas(self.compra, 3)
        self.cuota1, self.cuota2, self.cuota3 = self.compra.cuotas.order_by('numero')

    def test_pago_parcial_no_marca_pagada(self):
        registrar_pago_cuota(self.cuota1, Decimal('10.00'), timezone.localdate())
        self.cuota1.refresh_from_db()
        self.assertEqual(self.cuota1.saldo, Decimal('20.00'))
        self.assertEqual(self.cuota1.estado, 'pendiente')

    def test_pagar_todas_las_cuotas_marca_compra_pagada(self):
        for cuota in (self.cuota1, self.cuota2, self.cuota3):
            registrar_pago_cuota(cuota, cuota.saldo, timezone.localdate())
        self.compra.refresh_from_db()
        self.assertEqual(self.compra.estado, 'pagada')
        self.assertEqual(self.compra.saldo, Decimal('0.00'))

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

    def test_no_permite_pago_sobre_cuota_de_compra_anulada(self):
        self.compra.estado = 'anulada'
        self.compra.save()
        with self.assertRaises(ValueError):
            registrar_pago_cuota(self.cuota1, Decimal('5.00'), timezone.localdate())
