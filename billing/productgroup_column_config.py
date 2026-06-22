"""
Configuración centralizada de columnas disponibles para el módulo de
categorías (grupos de producto).
Esta configuración se utiliza en:
- Listado de categorías (product_group_list.html)
- Exportación PDF
- Exportación Excel
"""

PRODUCTGROUP_COLUMNS = {
    'name': {
        'label': 'Nombre',
        'field': 'name',
        'type': 'text',
        'width': 200,
        'visible': True,
        'required': True,  # Columna obligatoria
        'sortable': True,
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
        'visible': True,
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

PRODUCTGROUP_DEFAULT_VISIBLE_COLUMNS = [col for col, config in PRODUCTGROUP_COLUMNS.items() if config['visible']]


def get_productgroup_visible_columns(visible_list=None):
    """Obtener configuración de columnas visibles para categorías."""
    if visible_list is None:
        visible_list = PRODUCTGROUP_DEFAULT_VISIBLE_COLUMNS

    result = {}
    for col in visible_list:
        if col in PRODUCTGROUP_COLUMNS:
            result[col] = PRODUCTGROUP_COLUMNS[col]

    if not result and 'name' in PRODUCTGROUP_COLUMNS:
        result['name'] = PRODUCTGROUP_COLUMNS['name']

    return result


def get_all_productgroup_columns():
    """Retorna todas las columnas disponibles para categorías."""
    return PRODUCTGROUP_COLUMNS


def validate_productgroup_visible_columns(visible_list):
    """
    Validar que la lista de columnas visibles sea válida.
    Returns:
        Tupla (es_valida, columnas_validadas)
    """
    if not visible_list:
        return True, PRODUCTGROUP_DEFAULT_VISIBLE_COLUMNS

    valid_columns = [col for col in visible_list if col in PRODUCTGROUP_COLUMNS]

    if not valid_columns:
        valid_columns = PRODUCTGROUP_DEFAULT_VISIBLE_COLUMNS

    return True, valid_columns
