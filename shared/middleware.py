class NoCachePanelMiddleware:
    """Añade Cache-Control: no-store a todas las respuestas del panel.

    Impide que el navegador cachee páginas autenticadas: si el usuario
    cierra sesión y pulsa el botón "atrás", el browser hace un nuevo
    request al servidor en lugar de mostrar la versión en caché.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith('/panel/'):
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response['Pragma'] = 'no-cache'
        return response
