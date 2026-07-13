from django.contrib import admin
from .models import *

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ['name', 'whatsapp', 'is_active', 'created_at']
    search_fields = ['name']
    list_filter = ['is_active']
    fields = ['name', 'description', 'whatsapp', 'is_active']

@admin.register(ProductGroup)
class ProductGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active']

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ['name', 'contact_name', 'email', 'is_active']

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 3

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'brand', 'group', 'unit_price', 'stock']
    list_filter = ['brand', 'group']
    filter_horizontal = ['suppliers']
    inlines = [ProductImageInline]

class CustomerProfileInline(admin.StackedInline):
    model = CustomerProfile
    extra = 0; can_delete = False

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['dni', 'last_name', 'first_name', 'email']
    inlines = [CustomerProfileInline]

class InvoiceDetailInline(admin.TabularInline):
    model = InvoiceDetail; extra = 1

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['id', 'customer', 'invoice_date', 'total']
    inlines = [InvoiceDetailInline]

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['product', 'customer', 'rating', 'created_at']
    list_filter = ['rating', 'created_at']
    search_fields = ['product__name', 'customer__first_name', 'customer__last_name', 'customer__dni']
    readonly_fields = ['created_at', 'updated_at']

