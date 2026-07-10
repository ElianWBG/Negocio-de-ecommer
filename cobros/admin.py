from django.contrib import admin
from .models import CobroFactura


@admin.register(CobroFactura)
class CobroFacturaAdmin(admin.ModelAdmin):
    list_display = ('id', 'factura', 'fecha', 'valor')
    list_filter = ('fecha',)
