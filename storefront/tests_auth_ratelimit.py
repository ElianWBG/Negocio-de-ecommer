from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from billing.models import Customer


@override_settings(RATELIMIT_ENABLE=True)
class AuthHardeningRateLimitTestCase(TestCase):
    """Regresión del hardening de autenticación: login del panel, reset de
    contraseña y cambio de contraseña del cliente deben bloquear con 429 al
    superar su límite. Protege el orden de config/urls.py (nuestras vistas con
    rate limit deben preceder al include de auth.urls)."""

    def setUp(self):
        cache.clear()

    def test_login_staff_bloquea_fuerza_bruta(self):
        # RateLimitedLoginView: 5/min por IP.
        url = reverse('login')
        data = {'username': 'inexistente', 'password': 'incorrecta'}
        responses = [self.client.post(url, data) for _ in range(6)]
        self.assertTrue(all(r.status_code == 200 for r in responses[:5]))
        self.assertEqual(responses[5].status_code, 429)

    def test_password_reset_bloquea_email_bombing(self):
        # RateLimitedPasswordResetView: 5/hora por IP.
        url = reverse('password_reset')
        responses = [self.client.post(url, {'email': 'victima@example.com'}) for _ in range(6)]
        self.assertEqual(responses[5].status_code, 429)

    def test_change_password_bloquea_por_usuario(self):
        # change_password: 5/min por usuario.
        user = User.objects.create_user(username='cli_cp', password='CorrectHorse9')
        Customer.objects.create(dni='1710034065', first_name='C', last_name='P', user=user)
        self.client.force_login(user)
        url = reverse('storefront:change_password')
        data = {
            'current_password': 'incorrecta',
            'new_password1': 'NuevaClave123',
            'new_password2': 'NuevaClave123',
        }
        responses = [self.client.post(url, data) for _ in range(6)]
        self.assertEqual(responses[5].status_code, 429)
