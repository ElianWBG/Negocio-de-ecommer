from django.urls import path
from . import views

app_name = 'cobros'

urlpatterns = [
    path('', views.invoice_pending_list, name='invoice_pending_list'),
    path('factura/<int:factura_id>/registrar/', views.cobro_create, name='cobro_create'),
    path('factura/<int:factura_id>/historial/', views.payment_history, name='payment_history'),
    path('pago/<int:pk>/editar/', views.cobro_update, name='cobro_update'),
    path('pago/<int:pk>/eliminar/', views.cobro_delete, name='cobro_delete'),
]
