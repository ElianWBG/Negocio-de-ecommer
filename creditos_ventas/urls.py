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
]
