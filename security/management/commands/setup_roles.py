from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """
    Alias de 'setup_roles_full'. Existe un comando del mismo nombre en
    `billing` (versión histórica) que gana por orden de INSTALLED_APPS
    al invocar `manage.py setup_roles` — ese archivo delega aquí, y
    este delega en `setup_roles_full` para que el nombre 'setup_roles'
    funcione sin importar cuál de los dos se resuelva primero.
    """
    help = 'Alias de setup_roles_full.'

    def handle(self, *args, **options):
        call_command('setup_roles_full', *args, **options)
