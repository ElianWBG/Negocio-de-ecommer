from rest_framework import serializers

from .models import Factura


class ItemVentaSerializer(serializers.Serializer):
    codigo = serializers.CharField(max_length=25)
    descripcion = serializers.CharField(max_length=300)
    cantidad = serializers.DecimalField(max_digits=14, decimal_places=6)
    precio_unitario = serializers.DecimalField(max_digits=14, decimal_places=6)
    descuento = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, default=0
    )
    # Código de porcentaje de IVA del SRI: 0=0%, 2=12/15%, 6=No objeto, 7=Exento
    codigo_iva = serializers.CharField(max_length=2, required=False, default="2")


class VentaEntradaSerializer(serializers.Serializer):
    """Valida el JSON que envía el sistema principal."""

    cliente_identificacion = serializers.CharField(max_length=20)
    cliente_tipo_identificacion = serializers.CharField(max_length=2, default="05")
    cliente_razon_social = serializers.CharField(max_length=300)
    cliente_email = serializers.EmailField(required=False, allow_blank=True)
    cliente_direccion = serializers.CharField(
        max_length=300, required=False, allow_blank=True
    )
    cliente_telefono = serializers.CharField(
        max_length=30, required=False, allow_blank=True
    )
    items = ItemVentaSerializer(many=True)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("La venta debe tener al menos un ítem.")
        return value


class FacturaEstadoSerializer(serializers.ModelSerializer):
    """Respuesta ligera: estado + identificación del comprobante."""

    numero_comprobante = serializers.CharField(read_only=True)

    class Meta:
        model = Factura
        fields = [
            "id",
            "estado",
            "clave_acceso",
            "numero_comprobante",
            "numero_autorizacion",
            "mensaje_sri",
            "created_at",
        ]
