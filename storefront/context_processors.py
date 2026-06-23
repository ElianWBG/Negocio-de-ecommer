from billing.models import ConfigNegocio


def config_negocio(request):
    """Inyecta la configuración del negocio en todos los templates.
    Si la tabla no existe todavía (primer deploy), devuelve config por defecto."""
    if not hasattr(request, '_config_negocio_cache'):
        try:
            request._config_negocio_cache = ConfigNegocio.get()
        except Exception:
            # La tabla puede no existir en el primer arranque antes del migrate
            request._config_negocio_cache = ConfigNegocio()
    return {'config': request._config_negocio_cache}
