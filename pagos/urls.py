from django.urls import path
from . import views

app_name = 'pagos'

urlpatterns = [
    path('', views.purchase_pending_list, name='purchase_pending_list'),
    path('compra/<int:compra_id>/registrar/', views.pago_create, name='pago_create'),
    path('compra/<int:compra_id>/historial/', views.payment_history, name='payment_history'),
    path('pago/<int:pk>/editar/', views.pago_update, name='pago_update'),
    path('pago/<int:pk>/eliminar/', views.pago_delete, name='pago_delete'),
]
