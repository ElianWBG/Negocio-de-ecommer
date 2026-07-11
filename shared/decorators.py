import logging
from functools import wraps
from django.utils import timezone
from django.contrib import messages
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required


def group_required(*groups):
    """
    Decorador para FBVs. Exige pertenencia a al menos uno de los grupos indicados.
    Superusuarios pasan siempre.
    """
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_superuser:
                user_groups = set(request.user.groups.values_list('name', flat=True))
                if not user_groups.intersection(set(groups)):
                    messages.error(request, 'No tienes permisos para acceder a esta sección.')
                    return redirect('billing:home')
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator


def permission_required_any(*perms):
    """
    Decorador para FBVs. Exige al menos uno de los permisos indicados
    (formato 'app_label.codename'). Superusuarios pasan siempre.

    Uso:
        @permission_required_any('billing.view_invoice', 'billing.add_invoice')
        def invoice_list(request):
            ...
    """
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_superuser:
                if not any(request.user.has_perm(p) for p in perms):
                    messages.error(request, 'No tienes permisos para acceder a esta sección.')
                    return redirect('billing:home')
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator


# Configurar logger para auditoría
# Los mensajes se guardan en la consola y pueden redirigirse a archivo
logger = logging.getLogger('audit')


def audit_action(action_name):
    """
    Decorador que registra las acciones del usuario para auditoría.
    
    Parámetros:
        action_name (str): Nombre de la acción a registrar.
                          Ejemplo: "CREATE_BRAND", "DELETE_PRODUCT"
    
    Uso:
        @login_required
        @audit_action("CREATE_BRAND")
        def brand_create(request):
            ...
    
    ¿POR QUÉ?
    Para tener un registro de quién hizo qué en el sistema.
    Si un producto es eliminado, puedes rastrear quién lo hizo.
    
    ¿CÓMO FUNCIONA?
    1. El usuario llama a la vista (ej: brand_create)
    2. El decorador intercepta ANTES de ejecutar la vista
    3. Registra: usuario, acción, fecha/hora, método HTTP, IP
    4. Ejecuta la vista normalmente
    5. Si el método es POST (envío de formulario), registra también
       que la acción fue completada
    """

    def decorator(view_func):
        @wraps(view_func)  # Preserva el nombre y docstring de la vista original
        def wrapper(request, *args, **kwargs):

            # Obtener datos del usuario y la petición
            user = request.user.username if request.user.is_authenticated else 'Anonymous'
            ip = request.META.get('REMOTE_ADDR', 'unknown')  # IP del usuario
            method = request.method  # GET o POST
            timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
            path = request.path  # URL que visitó

            # Registrar la acción en el log
            logger.info(
                f'[AUDIT] {timestamp} | User: {user} | '
                f'Action: {action_name} | Method: {method} | '
                f'Path: {path} | IP: {ip}'
            )

            # También imprimir en consola para desarrollo
            print(
                f'\n[AUDIT] {timestamp} | User: {user} | '
                f'Action: {action_name} | Method: {method} | '
                f'Path: {path} | IP: {ip}'
            )

            # Ejecutar la vista original normalmente
            response = view_func(request, *args, **kwargs)

            # Si fue POST, registrar que la acción se completó
            if method == 'POST':
                print(f'[AUDIT] {timestamp} | COMPLETED: {action_name} by {user}')

            return response

        return wrapper
    return decorator
