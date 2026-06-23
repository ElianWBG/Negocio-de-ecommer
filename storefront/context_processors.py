from billing.models import ConfigNegocio


def config_negocio(request):
    """Inyecta la configuración del negocio en todos los templates.
    Usa caché de instancia para no hacer una query extra por cada
    template que se renderice en la misma request."""
    if not hasattr(request, '_config_negocio_cache'):
        request._config_negocio_cache = ConfigNegocio.get()
    return {'config': request._config_negocio_cache}
