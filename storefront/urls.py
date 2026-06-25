from django.urls import path
from . import views

app_name = 'storefront'

urlpatterns = [
    # Auth de clientes
    path('registro/', views.customer_register, name='customer_register'),
    path('login/', views.customer_login, name='customer_login'),
    path('logout/', views.customer_logout, name='customer_logout'),
    path('verificar-email/enviado/', views.verify_email_sent, name='verify_email_sent'),
    path('verificar-email/<str:token>/', views.verify_email, name='verify_email'),
    path('mis-pedidos/', views.my_orders, name='my_orders'),
    path('cambiar-contrasena/', views.change_password, name='change_password'),
    path('perfil/', views.profile, name='profile'),

    # Catálogo público
    path('', views.catalog_list, name='catalog_list'),
    path('producto/<int:pk>/', views.product_detail, name='product_detail'),

    # Carrito (sin login)
    path('carrito/', views.cart_view, name='cart_view'),
    path('carrito/agregar/<int:pk>/', views.cart_add, name='cart_add'),
    path('carrito/quitar/<int:pk>/', views.cart_remove, name='cart_remove'),
    path('carrito/actualizar/<int:pk>/', views.cart_update, name='cart_update'),

    # Checkout (requiere login)
    path('solicitar/', views.checkout, name='checkout'),
    path('solicitud/<int:pk>/pago/', views.payment_choice, name='payment_choice'),
    path('solicitud/<int:pk>/pago/manual/', views.pay_manual, name='pay_manual'),
    path('solicitud/<int:pk>/pago/tarjeta/', views.pay_with_card, name='pay_with_card'),
    path('solicitud/<int:pk>/pago/paypal/', views.pay_with_paypal, name='pay_with_paypal'),
    path('solicitud/<int:pk>/pago/paypal/capture/', views.paypal_capture, name='paypal_capture'),
    path('solicitud/<int:pk>/pago/exito/', views.payment_success, name='payment_success'),
    path('pago/payphone/respuesta/', views.payphone_response, name='payphone_response'),
    path('solicitud/<int:pk>/gracias/', views.request_success, name='request_success'),

    # Panel interno (requiere login de staff)
    path('panel/solicitudes/', views.purchase_request_list, name='purchase_request_list'),
    path('panel/solicitudes/<int:pk>/', views.purchase_request_detail, name='purchase_request_detail'),
    path('panel/solicitudes/<int:pk>/confirmar/', views.purchase_request_confirm, name='purchase_request_confirm'),
    path('panel/solicitudes/<int:pk>/rechazar/', views.purchase_request_reject, name='purchase_request_reject'),
]
