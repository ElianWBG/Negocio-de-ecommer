from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(RATELIMIT_ENABLE=True)
class LoginRateLimitTestCase(TestCase):
    """El login de clientes está protegido contra fuerza bruta: más de
    10 intentos por minuto desde la misma IP se bloquean con 429."""

    def setUp(self):
        cache.clear()

    def test_bloquea_tras_exceder_el_limite(self):
        url = reverse('storefront:customer_login')
        data = {'email': 'nadie@example.com', 'password': 'incorrecta'}

        responses = [self.client.post(url, data) for _ in range(11)]

        # Las primeras 10 se procesan normalmente (200: credenciales inválidas,
        # form re-renderizado); la 11a debe quedar bloqueada por el límite.
        self.assertTrue(all(r.status_code == 200 for r in responses[:10]))
        self.assertEqual(responses[10].status_code, 429)
