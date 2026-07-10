from django.contrib import admin
from .models import PagoCompra


@admin.register(PagoCompra)
class PagoCompraAdmin(admin.ModelAdmin):
    list_display = ('id', 'compra', 'fecha', 'valor')
    list_filter = ('fecha',)
