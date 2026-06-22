"""
Configuración centralizada de columnas disponibles para el módulo de
proveedores.
Esta configuración se utiliza en:
- Listado de proveedores (supplier_list.html)
- Exportación PDF
- Exportación Excel
"""

SUPPLIER_COLUMNS = {
    'name': {
        'label': 'Nombre',
        'field': 'name',
        'type': 'text',
        'width': 200,
        'visible': True,
        'required': True,  # Columna obligatoria
        'sortable': True,
    },
    'contact_name': {
        'label': 'Contacto',
        'field': 'contact_name',
        'type': 'text',
        'width': 180,
        'visible': True,
        'required': False,
        'sortable': True,
    },
    'email': {
        'label': 'Email',
        'field': 'email',
        'type': 'text',
        'width': 200,
        'visible': True,
        'required': False,
        'sortable': True,
    },
    'phone': {
        'label': 'Teléfono',
        'field': 'phone',
        'type': 'text',
        'width': 130,
        'visible': True,
        'required': False,
        'sortable': False,
    },
    'address': {
        'label': 'Dirección',
        'field': 'address',
        'type': 'text',
        'width': 250,
        'visible': False,
        'required': False,
        'sortable': False,
    },
    'product_count': {
        'label': 'Productos',
        'field': 'product_count',
        'type': 'count',
        'width': 100,
        'visible': False,
        'required': False,
        'sortable': False,
    },
    'is_active': {
        'label': 'Estado',
        'field': 'is_active',
        'type': 'boolean',
        'width': 100,
        'visible': True,
        'required': False,
        'sortable': True,
    },
    'created_at': {
        'label': 'Fecha creación',
        'field': 'created_at',
        'type': 'datetime',
        'width': 150,
        'visible': False,
        'required': False,
        'sortable': True,
    },
    'updated_at': {
        'label': 'Última actualización',
        'field': 'updated_at',
        'type': 'datetime',
        'width': 150,
        'visible': False,
        'required': False,
        'sortable': True,
    },
}

SUPPLIER_DEFAULT_VISIBLE_COLUMNS = [col for col, config in SUPPLIER_COLUMNS.items() if config['visible']]


def get_supplier_visible_columns(visible_list=None):
    """Obtener configuración de columnas visibles para proveedores."""
    if visible_list is None:
        visible_list = SUPPLIER_DEFAULT_VISIBLE_COLUMNS

    result = {}
    for col in visible_list:
        if col in SUPPLIER_COLUMNS:
            result[col] = SUPPLIER_COLUMNS[col]

    if not result and 'name' in SUPPLIER_COLUMNS:
        result['name'] = SUPPLIER_COLUMNS['name']

    return result


def get_all_supplier_columns():
    """Retorna todas las columnas disponibles para proveedores."""
    return SUPPLIER_COLUMNS


def validate_supplier_visible_columns(visible_list):
    """
    Validar que la lista de columnas visibles sea válida.
    Returns:
        Tupla (es_valida, columnas_validadas)
    """
    if not visible_list:
        return True, SUPPLIER_DEFAULT_VISIBLE_COLUMNS

    valid_columns = [col for col in visible_list if col in SUPPLIER_COLUMNS]

    if not valid_columns:
        valid_columns = SUPPLIER_DEFAULT_VISIBLE_COLUMNS

    return True, valid_columns
