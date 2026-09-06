from django.contrib.auth.views import (
    LoginView,
    PasswordResetView,
    PasswordResetConfirmView,
)
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit


# El login del panel interno (/accounts/login/) es el objetivo de mayor valor
# del sistema: da acceso a la gestión del negocio. La vista por defecto de
# Django no trae protección de fuerza bruta, así que aquí la añadimos igual
# que en el login público de clientes (storefront.views.customer_login).
#
# 5 intentos por minuto y por IP: suficiente para un humano que se equivoca de
# contraseña, pero inservible para un bot que prueba miles de combinaciones.
# Al superarlo, django-ratelimit lanza Ratelimited y RATELIMIT_VIEW
# (shared.ratelimit.ratelimited_view) responde con un 429.
@method_decorator(
    ratelimit(key='ip', rate='5/m', method='POST', block=True),
    name='post',
)
class RateLimitedLoginView(LoginView):
    pass


# Reset de contraseña: la vista por defecto de Django envía un correo por cada
# POST. Sin límite, un atacante puede usarla para bombardear de correos a una
# víctima (poniendo su email una y otra vez) o para saturar el proveedor de
# email. 5 solicitudes por hora y por IP: cubre de sobra los reintentos
# legítimos de alguien que no recibió el correo, y corta el abuso.
@method_decorator(
    ratelimit(key='ip', rate='5/h', method='POST', block=True),
    name='post',
)
class RateLimitedPasswordResetView(PasswordResetView):
    pass


# Confirmación del reset (fijar la nueva contraseña con uid+token de la URL).
# Los tokens de Django son criptográficamente fuertes, pero limitar los POST
# frena por completo cualquier intento de fuerza bruta sobre el token y es una
# defensa en profundidad barata. 10/min por IP no molesta a un usuario real.
@method_decorator(
    ratelimit(key='ip', rate='10/m', method='POST', block=True),
    name='post',
)
class RateLimitedPasswordResetConfirmView(PasswordResetConfirmView):
    pass
