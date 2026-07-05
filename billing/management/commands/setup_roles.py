from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission


ROLES = {
    'Administrador': [],  # permissions granted via superuser or manually
    'Vendedor': [],
    'Analista de Compras': [],
}


class Command(BaseCommand):
    help = 'Crea los grupos de roles del panel (Administrador, Vendedor, Analista de Compras)'

    def handle(self, *args, **options):
        for name in ROLES:
            group, created = Group.objects.get_or_create(name=name)
            if created:
                self.stdout.write(self.style.SUCCESS(f'  Grupo creado: {name}'))
            else:
                self.stdout.write(f'  Grupo ya existe: {name}')

        self.stdout.write(self.style.SUCCESS('setup_roles completado.'))
