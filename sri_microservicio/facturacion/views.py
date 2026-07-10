from decimal import Decimal

from django.conf import settings
from rest_framework import status
from rest_framework.generics import RetrieveAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Factura
from .secuencia import siguiente_secuencial
from .serializers import FacturaEstadoSerializer, VentaEntradaSerializer
from .tasks import emitir_factura


class EmitirFacturaView(APIView):
    """
    POST /api/v1/facturas/
    Recibe la venta, crea la Factura en PENDIENTE, responde 202 y
    dispara el procesamiento en segundo plano (Celery).
    """

    def post(self, request):
        serializer = VentaEntradaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Totales calculados a partir de los ítems
        subtotal = Decimal("0")
        iva = Decimal("0")
        for it in data["items"]:
            base = (it["cantidad"] * it["precio_unitario"]) - it.get("descuento", 0)
            subtotal += base
            if it.get("codigo_iva", "2") == "2":       # tarifa vigente (12/15%)
                iva += (base * Decimal("0.15")).quantize(Decimal("0.01"))

        emisor = settings.EMISOR
        factura = Factura.objects.create(
            estado=Factura.Estado.PENDIENTE,
            ambiente=settings.SRI["AMBIENTE"],
            establecimiento=emisor["ESTABLECIMIENTO"],
            punto_emision=emisor["PUNTO_EMISION"],
            secuencial=siguiente_secuencial(
                emisor["ESTABLECIMIENTO"], emisor["PUNTO_EMISION"]
            ),
            cliente_identificacion=data["cliente_identificacion"],
            cliente_tipo_identificacion=data["cliente_tipo_identificacion"],
            cliente_razon_social=data["cliente_razon_social"],
            cliente_email=data.get("cliente_email", ""),
            cliente_direccion=data.get("cliente_direccion", ""),
            cliente_telefono=data.get("cliente_telefono", ""),
            subtotal=subtotal,
            iva=iva,
            total=subtotal + iva,
            payload=request.data,
        )

        # Procesamiento asíncrono — NO bloquea la respuesta.
        emitir_factura.delay(factura.id)

        return Response(
            FacturaEstadoSerializer(factura).data,
            status=status.HTTP_202_ACCEPTED,
        )


class FacturaEstadoView(RetrieveAPIView):
    """GET /api/v1/facturas/<id>/  — consulta el estado del comprobante."""

    queryset = Factura.objects.all()
    serializer_class = FacturaEstadoSerializer
