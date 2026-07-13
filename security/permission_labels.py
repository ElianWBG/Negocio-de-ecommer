"""Traducción de permisos de Django a etiquetas legibles en español,
sin tocar Permission.name en la base de datos (evita desincronizarse
en el próximo `migrate` y no depende de una migración de datos)."""

ACTION_LABELS_ES = {
    'add': 'Crear',
    'change': 'Editar',
    'delete': 'Eliminar',
    'view': 'Ver',
    'export': 'Exportar/descargar',
}

APP_SECTION_LABELS_ES = {
    'billing': 'Catálogo, ventas y clientes',
    'purchasing': 'Compras a proveedores',
    'cobros': 'Cuentas por cobrar',
    'pagos': 'Cuentas por pagar',
    'creditos_compras': 'Cuotas de compras a crédito',
    'creditos_ventas': 'Cuotas de ventas a crédito',
    'storefront': 'Tienda y pedidos de clientes',
    'auth': 'Usuarios y roles del sistema',
    'admin': 'Registros de administración (sistema)',
    'contenttypes': 'Tipos de contenido (sistema)',
    'sessions': 'Sesiones (sistema)',
}


def app_section_label(app_label):
    return APP_SECTION_LABELS_ES.get(app_label, app_label.capitalize())


def permission_label_es(permission):
    """'Can view Marca' -> 'Ver marca'. Si el codename no sigue el
    patrón CRUD estándar (permiso custom), cae en permission.name tal cual."""
    codename = permission.codename
    prefix, _, rest = codename.partition('_')
    if prefix in ACTION_LABELS_ES and rest:
        model = permission.content_type.model_class()
        model_name = model._meta.verbose_name if model else rest
        return f'{ACTION_LABELS_ES[prefix]} {model_name}'
    return permission.name
