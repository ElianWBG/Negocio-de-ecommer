from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission

from security.role_presets import ROLES


class Command(BaseCommand):
    help = 'Crea/actualiza los roles del sistema con sus permisos (invocado como "setup_roles")'

    def handle(self, *args, **kwargs):
        for role_name, codenames in ROLES.items():
            # get_or_create: si el rol ya existe NO lo duplica
            group, created = Group.objects.get_or_create(name=role_name)

            if codenames == '__all__':
                # Nunca incluir permisos de auth.* en el preset "todos los permisos":
                # un Administrador no-superusuario nunca debe poder gestionar usuarios/
                # permisos/grupos de Django (mismo criterio que _StripAuthPermissionsMixin
                # en security/views.py). Los superusuarios reales no se ven afectados,
                # ya que ignoran las verificaciones de permisos.
                perms = Permission.objects.exclude(content_type__app_label='auth')
            else:
                perms = Permission.objects.filter(codename__in=codenames)

            # set() reemplaza los permisos del rol por esta lista
            group.permissions.set(perms)

            status = 'creado' if created else 'actualizado'
            self.stdout.write(self.style.SUCCESS(
                f'Rol "{role_name}" {status} con {perms.count()} permisos'
            ))
