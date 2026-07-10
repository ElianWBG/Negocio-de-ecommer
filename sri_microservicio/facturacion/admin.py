from django.contrib import admin

from .models import Factura


@admin.register(Factura)
class FacturaAdmin(admin.ModelAdmin):
    list_display = (
        "numero_comprobante",
        "estado",
        "cliente_razon_social",
        "total",
        "clave_acceso",
        "created_at",
    )
    list_filter = ("estado", "ambiente")
    search_fields = ("clave_acceso", "cliente_identificacion", "cliente_razon_social")
    readonly_fields = ("clave_acceso", "numero_autorizacion", "created_at", "updated_at")
