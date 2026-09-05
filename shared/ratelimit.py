from django.http import HttpResponse


def ratelimited_view(request, exception):
    """Respuesta cuando django-ratelimit bloquea una petición (demasiados
    intentos desde la misma IP en poco tiempo: login, registro, checkout,
    pagos). 429 = Too Many Requests, el código HTTP correcto para esto."""
    return HttpResponse(
        'Demasiados intentos. Espera un momento e inténtalo de nuevo.',
        status=429,
        content_type='text/plain; charset=utf-8',
    )
