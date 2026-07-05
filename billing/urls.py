from django.urls import path
from . import views
app_name = 'billing'
urlpatterns = [
    path('', views.home, name='home'),
    path('signup/', views.SignUpView.as_view(), name='signup'),
    
    # Brand (FBV)
    path('brands/', views.brand_list, name='brand_list'),
    path('brands/create/', views.brand_create, name='brand_create'),
    path('brands/<int:pk>/', views.brand_detail, name='brand_detail'),
    path('brands/<int:pk>/edit/', views.brand_update, name='brand_update'),
    path('brands/<int:pk>/delete/', views.brand_delete, name='brand_delete'),
    path('brands/api/update-visible-columns/', views.brand_update_visible_columns, name='brand_update_visible_columns'),

    # ProductGroup
    path('groups/', views.ProductGroupListView.as_view(), name='productgroup_list'),
    path('groups/create/', views.ProductGroupCreateView.as_view(), name='productgroup_create'),
    path('groups/<int:pk>/', views.ProductGroupDetailView.as_view(), name='productgroup_detail'),
    path('groups/<int:pk>/edit/', views.ProductGroupUpdateView.as_view(), name='productgroup_update'),
    path('groups/<int:pk>/delete/', views.ProductGroupDeleteView.as_view(), name='productgroup_delete'),
    path('groups/api/update-visible-columns/', views.productgroup_update_visible_columns, name='productgroup_update_visible_columns'),

    # SupplierGroup
    path('suppliers/', views.SupplierListView.as_view(), name='supplier_list'),
    path('suppliers/create/', views.SupplierCreateView.as_view(), name='supplier_create'),
    path('suppliers/<int:pk>/', views.SupplierDetailView.as_view(), name='supplier_detail'),
    path('suppliers/<int:pk>/edit/', views.SupplierUpdateView.as_view(), name='supplier_update'),
    path('suppliers/<int:pk>/delete/', views.SupplierDeleteView.as_view(), name='supplier_delete'),
    path('suppliers/api/update-visible-columns/', views.supplier_update_visible_columns, name='supplier_update_visible_columns'),

    # Product
    path('products/', views.ProductListView.as_view(), name='product_list'),
    path('products/import/', views.product_import, name='product_import'),
    path('products/import/template/', views.product_import_template, name='product_import_template'),
    path('products/create/', views.ProductCreateView.as_view(), name='product_create'),
    path('products/<int:pk>/', views.ProductDetailView.as_view(), name='product_detail'),
    path('products/<int:pk>/update-image/', views.product_update_image, name='product_update_image'),
    path('products/<int:pk>/edit/', views.ProductUpdateView.as_view(), name='product_update'),
    path('products/<int:pk>/delete/', views.ProductDeleteView.as_view(), name='product_delete'),
    path('products/api/update-visible-columns/', views.product_update_visible_columns, name='product_update_visible_columns'),

    # Customer
    path('customers/', views.CustomerListView.as_view(), name='customer_list'),
    path('customers/import/', views.customer_import, name='customer_import'),
    path('customers/import/template/', views.customer_import_template, name='customer_import_template'),
    path('customers/create/', views.CustomerCreateView.as_view(), name='customer_create'),
    path('customers/<int:pk>/', views.CustomerDetailView.as_view(), name='customer_detail'),
    path('customers/<int:pk>/edit/', views.CustomerUpdateView.as_view(), name='customer_update'),
    path('customers/<int:pk>/delete/', views.CustomerDeleteView.as_view(), name='customer_delete'),
    path('customers/api/update-visible-columns/', views.customer_update_visible_columns, name='customer_update_visible_columns'),

    # Invoice
    path('invoices/', views.InvoiceListView.as_view(), name='invoice_list'),
    path('invoices/create/', views.invoice_create, name='invoice_create'),
    path('invoices/<int:pk>/', views.InvoiceDetailView.as_view(), name='invoice_detail'),
    path('invoices/<int:pk>/delete/', views.InvoiceDeleteView.as_view(), name='invoice_delete'),
    path('invoices/api/update-visible-columns/', views.invoice_update_visible_columns, name='invoice_update_visible_columns'),

    # API
    path('api/product-info/<int:pk>/', views.api_product_info, name='api_product_info'),

    # Reportes
    path('reportes/ventas/', views.report_sales, name='report_sales'),
    path('reportes/ventas/excel/', views.report_sales_excel, name='report_sales_excel'),
    path('reportes/ventas/pdf/', views.report_sales_pdf, name='report_sales_pdf'),
    path('reportes/stock/', views.report_stock, name='report_stock'),
    path('reportes/stock/excel/', views.report_stock_excel, name='report_stock_excel'),

    # Configuración del negocio
    path('configuracion/', views.config_negocio_edit, name='config_negocio'),

    # Gestión de usuarios
    path('usuarios/', views.user_management, name='user_management'),

]