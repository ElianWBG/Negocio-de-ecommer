from django.db import models


class Factura(models.Model):
    """Comprobante electrónico y su ciclo de vida en el esquema offline del SRI."""

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"      # creada, aún no enviada
        ENVIADO = "ENVIADO", "Enviado"            # recibida por el SRI (RECIBIDA)
        AUTORIZADO = "AUTORIZADO", "Autorizado"   # autorizada por el SRI
        RECHAZADO = "RECHAZADO", "Rechazado"      # recepción DEVUELTA / no autorizada
        DEVUELTO = "DEVUELTO", "Devuelto"         # recepción con errores (DEVUELTA)

    # --- Identificación del comprobante ---
    estado = models.CharField(
        max_length=12, choices=Estado.choices, default=Estado.PENDIENTE, db_index=True
    )
    clave_acceso = models.CharField(max_length=49, unique=True, blank=True, db_index=True)
    numero_autorizacion = models.CharField(max_length=49, blank=True)
    fecha_autorizacion = models.DateTimeField(null=True, blank=True)

    # Secuencial 001-001-000000123
    establecimiento = models.CharField(max_length=3)
    punto_emision = models.CharField(max_length=3)
    secuencial = models.CharField(max_length=9)
    ambiente = models.CharField(max_length=1, default="1")  # 1=Pruebas, 2=Producción

    # --- Cliente / receptor ---
    cliente_identificacion = models.CharField(max_length=20)
    cliente_tipo_identificacion = models.CharField(max_length=2, default="05")  # 04 RUC, 05 Cédula, 06 Pasaporte, 07 Consumidor final
    cliente_razon_social = models.CharField(max_length=300)
    cliente_email = models.EmailField(blank=True)
    cliente_direccion = models.CharField(max_length=300, blank=True)
    cliente_telefono = models.CharField(max_length=30, blank=True)

    # --- Totales ---
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    iva = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # Detalle original recibido del sistema principal (JSON)
    payload = models.JSONField(default=dict)

    # --- Archivos generados ---
    xml_path = models.CharField(max_length=500, blank=True)      # XML firmado
    xml_autorizado_path = models.CharField(max_length=500, blank=True)
    pdf_path = models.CharField(max_length=500, blank=True)      # RIDE

    # --- Trazabilidad ---
    mensaje_sri = models.TextField(blank=True)   # errores / mensajes devueltos
    intentos = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["estado", "created_at"])]

    def __str__(self):
        return f"{self.numero_comprobante} · {self.estado}"

    @property
    def numero_comprobante(self):
        return f"{self.establecimiento}-{self.punto_emision}-{self.secuencial}"

    def marcar(self, estado, mensaje=""):
        self.estado = estado
        if mensaje:
            self.mensaje_sri = mensaje
        self.save(update_fields=["estado", "mensaje_sri", "updated_at"])
