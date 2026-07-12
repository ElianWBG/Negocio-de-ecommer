from django.contrib import admin
from .models import CuotaCompra, PagoCuotaCompra


@admin.register(CuotaCompra)
class CuotaCompraAdmin(admin.ModelAdmin):
    list_display = ('id', 'compra', 'numero', 'fecha_vencimiento', 'valor', 'saldo', 'estado')
    list_filter = ('estado', 'fecha_vencimiento')


@admin.register(PagoCuotaCompra)
class PagoCuotaCompraAdmin(admin.ModelAdmin):
    list_display = ('id', 'cuota', 'fecha', 'valor')
    list_filter = ('fecha',)
