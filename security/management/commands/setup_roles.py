from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission

# Diccionario: rol -> lista de codenames de permisos
ROLES = {
    # El Administrador recibe TODOS los permisos
    'Administrador': '__all__',

    # El Vendedor gestiona clientes y facturas (y VE productos)
    'Vendedor': [
        'view_customer', 'add_customer', 'change_customer',
        'view_customerprofile', 'add_customerprofile', 'change_customerprofile',
        'view_invoice', 'add_invoice', 'change_invoice',
        'view_invoicedetail', 'add_invoicedetail', 'change_invoicedetail',
        'view_product',
    ],

    # El Analista de Compras gestiona el catálogo completo
    'Analista de Compras': [
        'view_brand', 'add_brand', 'change_brand', 'delete_brand',
        'view_productgroup', 'add_productgroup', 'change_productgroup', 'delete_productgroup',
        'view_supplier', 'add_supplier', 'change_supplier', 'delete_supplier',
        'view_product', 'add_product', 'change_product', 'delete_product',
    ],
}

class Command(BaseCommand):
    help = 'Crea los 3 roles del sistema con sus permisos'

    def handle(self, *args, **kwargs):
        for role_name, codenames in ROLES.items():
            # get_or_create: si el rol ya existe NO lo duplica
            group, created = Group.objects.get_or_create(name=role_name)

            if codenames == '__all__':
                perms = Permission.objects.all()
            else:
                perms = Permission.objects.filter(codename__in=codenames)

            # set() reemplaza los permisos del rol por esta lista
            group.permissions.set(perms)

            status = 'creado' if created else 'actualizado'
            self.stdout.write(self.style.SUCCESS(
                f'Rol "{role_name}" {status} con {perms.count()} permisos'
            ))
