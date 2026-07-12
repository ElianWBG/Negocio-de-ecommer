from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission

# Diccionario: rol -> lista de codenames de permisos.
# Los codenames son los automáticos que Django genera por modelo
# (view_/add_/change_/delete_<modelo>), no se inventan permisos custom.
# Nota: si algún día dos apps distintas usan el mismo codename para
# modelos distintos, hay que filtrar por content_type__app_label además
# de codename — hoy no hay colisiones en este proyecto.
ROLES = {
    # El Administrador recibe TODOS los permisos
    'Administrador': '__all__',

    # El Vendedor gestiona clientes, facturas y aprueba pedidos de la tienda
    'Vendedor': [
        'view_customer', 'add_customer', 'change_customer', 'delete_customer',
        'view_customerprofile', 'add_customerprofile', 'change_customerprofile',
        'view_invoice', 'add_invoice', 'change_invoice', 'delete_invoice',
        'view_invoicedetail', 'add_invoicedetail', 'change_invoicedetail',
        'view_product',
        # Aprobar/rechazar pedidos hechos desde la tienda
        'view_purchaserequest', 'change_purchaserequest',
        # Generar el cronograma de cuotas de una factura a crédito
        'view_cuotaventa', 'add_cuotaventa',
    ],

    # El Analista de Compras gestiona el catálogo completo y las compras a proveedores
    'Analista de Compras': [
        'view_brand', 'add_brand', 'change_brand', 'delete_brand',
        'view_productgroup', 'add_productgroup', 'change_productgroup', 'delete_productgroup',
        'view_supplier', 'add_supplier', 'change_supplier', 'delete_supplier',
        'view_product', 'add_product', 'change_product', 'delete_product',
        # Compras a proveedores
        'view_purchase', 'add_purchase', 'delete_purchase',
        # Generar el cronograma de cuotas de una compra a crédito
        'view_cuotacompra', 'add_cuotacompra',
    ],

    # Contador / Finanzas: cuentas por cobrar/pagar y reportes financieros
    'Contador': [
        'view_cobrofactura', 'add_cobrofactura', 'change_cobrofactura', 'delete_cobrofactura',
        'view_pagocompra', 'add_pagocompra', 'change_pagocompra', 'delete_pagocompra',
        'view_cuotacompra', 'change_cuotacompra',
        'view_pagocuotacompra', 'add_pagocuotacompra',
        'view_cuotaventa', 'change_cuotaventa',
        'view_pagocuotaventa', 'add_pagocuotaventa',
        'view_invoice', 'view_purchase', 'view_invoicedetail', 'view_product', 'view_customer', 'view_supplier',
    ],

    # Atención al Cliente: solo revisa y aprueba/rechaza pedidos de la tienda
    'Atención al Cliente': [
        'view_purchaserequest', 'change_purchaserequest',
    ],
}

class Command(BaseCommand):
    help = 'Crea/actualiza los roles del sistema con sus permisos (invocado como "setup_roles")'

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
