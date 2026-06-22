from django.contrib import admin
from .models import Purchase, PurchaseDetail


class PurchaseDetailInline(admin.TabularInline):
    model = PurchaseDetail
    extra = 1


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ['id', 'supplier', 'document_number', 'purchase_date', 'total']
    list_filter = ['supplier', 'is_active']
    search_fields = ['document_number', 'supplier__name']
    inlines = [PurchaseDetailInline]
