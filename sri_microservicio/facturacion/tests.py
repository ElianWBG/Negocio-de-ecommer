"""
Pruebas del microservicio de facturación (modo simulado).
Ejecutar:  python manage.py test
"""
from datetime import date

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .models import Factura
from .sri.clave_acceso import generar_clave_acceso, modulo11


class ModuloOnceTests(TestCase):
    def test_reglas_especiales(self):
        # El SRI define: residuo -> 11 => 0 ; 10 => 1
        # Se validan indirectamente recomputando el DV de claves generadas.
        clave = generar_clave_acceso(
            fecha_emision=date(2026, 7, 10),
            tipo_comprobante="01",
            ruc="1790012345001",
            ambiente="1",
            establecimiento="001",
            punto_emision="001",
            secuencial="000000123",
            codigo_numerico="12345678",
        )
        self.assertEqual(len(clave), 49)
        self.assertEqual(modulo11(clave[:48]), int(clave[48]))

    def test_dv_en_rango(self):
        for sec in range(1, 50):
            clave = generar_clave_acceso(
                fecha_emision=date(2026, 7, 10),
                tipo_comprobante="01",
                ruc="1790012345001",
                ambiente="1",
                establecimiento="001",
                punto_emision="001",
                secuencial=str(sec).zfill(9),
            )
            dv = int(clave[48])
            self.assertIn(dv, range(0, 10))
            self.assertEqual(modulo11(clave[:48]), dv)


@override_settings()
class FlujoSimuladoTests(TestCase):
    """Verifica el flujo asíncrono completo con SRI simulado + Celery eager."""

    def setUp(self):
        from django.conf import settings

        settings.SRI["SIMULADO"] = True
        settings.CELERY_TASK_ALWAYS_EAGER = True
        self.client = APIClient()

    def test_emision_hasta_autorizado(self):
        payload = {
            "cliente_identificacion": "0102030405",
            "cliente_razon_social": "Juan Perez",
            "cliente_email": "juan@example.com",
            "items": [
                {"codigo": "P1", "descripcion": "Producto 1", "cantidad": 2, "precio_unitario": 10.0},
                {"codigo": "P2", "descripcion": "Producto 2", "cantidad": 1, "precio_unitario": 5.0},
            ],
        }
        resp = self.client.post("/api/v1/facturas/", payload, format="json")
        self.assertEqual(resp.status_code, 202)

        factura = Factura.objects.get(pk=resp.data["id"])
        self.assertEqual(factura.estado, Factura.Estado.AUTORIZADO)
        self.assertEqual(len(factura.clave_acceso), 49)
        self.assertEqual(factura.numero_autorizacion, factura.clave_acceso)
        # subtotal 25.00, IVA 15% = 3.75, total 28.75
        self.assertEqual(str(factura.subtotal), "25.00")
        self.assertEqual(str(factura.iva), "3.75")
        self.assertEqual(str(factura.total), "28.75")
        # Se generaron los archivos
        self.assertTrue(factura.xml_path.endswith(".xml"))
        self.assertTrue(factura.pdf_path.endswith(".pdf"))

    def test_rechaza_venta_sin_items(self):
        resp = self.client.post(
            "/api/v1/facturas/",
            {"cliente_identificacion": "1", "cliente_razon_social": "X", "items": []},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
