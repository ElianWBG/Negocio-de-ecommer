from django.urls import path
from . import views

app_name = 'creditos_ventas'

urlpatterns = [
    path('pendientes/', views.cuotas_pendientes_list, name='cuotas_pendientes_list'),
    path('factura/<int:factura_id>/generar/', views.generar_cuotas_view, name='generar_cuotas'),
    path('factura/<int:factura_id>/cuotas/', views.cuota_list, name='cuota_list'),
    path('cuota/<int:pk>/pagar/', views.pago_cuota_create, name='pago_cuota_create'),
    path('cuota/<int:pk>/historial/', views.cuota_payment_history, name='cuota_payment_history'),
    path('cuota/<int:pk>/comprobante/', views.comprobante_cuota, name='comprobante_cuota'),
    path('cuota/<int:pk>/pagar-paypal/', views.pagar_cuota_paypal, name='pagar_cuota_paypal'),
    path('cuota/<int:pk>/pagar-paypal/create-order/', views.paypal_create_order_cuota, name='paypal_create_order_cuota'),
    path('cuota/<int:pk>/pagar-paypal/capture/', views.paypal_capture_cuota, name='paypal_capture_cuota'),
    path('pago/<int:pk>/recibo/', views.recibo_pago, name='recibo_pago'),
]
