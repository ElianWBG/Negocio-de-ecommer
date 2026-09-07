from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from axes.utils import reset


@override_settings(AXES_ENABLED=True)
class AxesAccountLockoutTestCase(TestCase):
    """Bloqueo de login por CUENTA (django-axes). A diferencia del rate limit
    por IP, tras 5 intentos fallidos la cuenta queda bloqueada aunque después
    se use la contraseña correcta (prueba de que el bloqueo es por cuenta y no
    solo por volumen de peticiones). El rate limit por IP está desactivado en
    tests, así que el 429 aquí proviene exclusivamente de axes."""

    def setUp(self):
        cache.clear()
        reset()  # limpia cualquier intento previo registrado por axes
        self.user = User.objects.create_user(
            username='staff_axes', password='ClaveCorrecta123', is_staff=True,
        )

    def tearDown(self):
        reset()

    def test_bloquea_la_cuenta_tras_cinco_fallos(self):
        url = reverse('login')
        for _ in range(5):
            self.client.post(url, {'username': 'staff_axes', 'password': 'incorrecta'})
        # Cuenta bloqueada: incluso con la contraseña CORRECTA la respuesta es 429.
        resp = self.client.post(url, {'username': 'staff_axes', 'password': 'ClaveCorrecta123'})
        self.assertEqual(resp.status_code, 429)
