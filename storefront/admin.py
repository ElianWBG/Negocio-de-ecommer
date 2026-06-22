from django.contrib import admin
from .models import PurchaseRequest, PurchaseRequestDetail


class PurchaseRequestDetailInline(admin.TabularInline):
    model = PurchaseRequestDetail
    extra = 0


@admin.register(PurchaseRequest)
class PurchaseRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'status', 'created_at', 'reviewed_at')
    list_filter = ('status',)
    inlines = [PurchaseRequestDetailInline]
