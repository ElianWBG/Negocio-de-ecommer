"""Traducción de permisos de Django a etiquetas legibles en español,
sin tocar Permission.name en la base de datos."""

ACTION_LABELS_ES = {
    'add': 'Crear',
    'change': 'Editar',
    'delete': 'Eliminar',
    'view': 'Ver',
    'export': 'Exportar/descargar',
}

# Sección por modelo específico (app_label, model_name) → título del bloque
MODEL_SECTION_LABELS_ES = {
    # Clientes
    ('billing', 'customer'):        'Clientes',
    ('billing', 'customerprofile'): 'Clientes',
    # Facturas y ventas
    ('billing', 'invoice'):        'Facturas y ventas',
    ('billing', 'invoicedetail'):  'Facturas y ventas',
    ('billing', 'invoicepayment'): 'Facturas y ventas',
    # Catálogo — Productos
    ('billing', 'product'):        'Catálogo — Productos',
    ('billing', 'productgroup'):   'Catálogo — Productos',
    ('billing', 'productimage'):   'Catálogo — Productos',
    # Catálogo — Marcas y proveedores
    ('billing', 'brand'):    'Catálogo — Marcas y proveedores',
    ('billing', 'supplier'): 'Catálogo — Marcas y proveedores',
    # Reseñas
    ('billing', 'review'):      'Reseñas de productos',
    ('billing', 'reviewimage'): 'Reseñas de productos',
    # Configuración
    ('billing', 'confignegocio'):         'Configuración del negocio',
    ('billing', 'panelverificationcode'): 'Configuración del negocio',
    # Auditoría
    ('billing', 'auditlog'): 'Auditoría y reportes',
}

# Sección por app completa (fallback cuando el modelo no está en MODEL_SECTION_LABELS_ES)
APP_SECTION_LABELS_ES = {
    'purchasing':      'Compras a proveedores',
    'cobros':          'Cuentas por cobrar',
    'pagos':           'Cuentas por pagar',
    'creditos_compras': 'Cuotas de compras a crédito',
    'creditos_ventas':  'Cuotas de ventas a crédito',
    'storefront':      'Tienda y pedidos de clientes',
    'auth':            'Usuarios y roles del sistema',
    'admin':           'Administración (sistema)',
    'contenttypes':    'Tipos de contenido (sistema)',
    'sessions':        'Sesiones (sistema)',
}

# Orden de aparición de las secciones en el formulario
SECTION_SORT_ORDER = [
    'Clientes',
    'Facturas y ventas',
    'Catálogo — Productos',
    'Catálogo — Marcas y proveedores',
    'Reseñas de productos',
    'Tienda y pedidos de clientes',
    'Compras a proveedores',
    'Cuentas por cobrar',
    'Cuentas por pagar',
    'Cuotas de ventas a crédito',
    'Cuotas de compras a crédito',
    'Auditoría y reportes',
    'Configuración del negocio',
    'Usuarios y roles del sistema',
    'Administración (sistema)',
]


def model_section_label(app_label: str, model_name: str) -> str:
    key = (app_label, model_name)
    if key in MODEL_SECTION_LABELS_ES:
        return MODEL_SECTION_LABELS_ES[key]
    return APP_SECTION_LABELS_ES.get(app_label, app_label.capitalize())


def permission_label_es(permission) -> str:
    codename = permission.codename
    prefix, _, rest = codename.partition('_')
    if prefix in ACTION_LABELS_ES and rest:
        model = permission.content_type.model_class()
        model_name = model._meta.verbose_name if model else rest
        return f'{ACTION_LABELS_ES[prefix]} {model_name}'
    return permission.name
