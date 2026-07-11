from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """
    Este comando vivía aquí con una versión antigua que solo creaba
    grupos vacíos (sin permisos). La versión completa (crea los roles
    y les asigna sus permisos) ahora vive en `security`, que se carga
    después de `billing` en INSTALLED_APPS y por lo tanto sería
    ignorada si este archivo se elimina sin más — así que en vez de
    borrar el archivo, delega en la versión real para no dejar dos
    comandos con el mismo nombre y comportamiento distinto.
    """
    help = 'Delega en security.setup_roles (versión con permisos).'

    def handle(self, *args, **options):
        call_command('setup_roles_full', *args, **options)
