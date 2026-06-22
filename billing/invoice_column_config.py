"""
Configuración centralizada de columnas disponibles para el módulo de facturas.
Esta configuración se utiliza en:
- Listado de facturas (invoice_list.html)
- Exportación PDF
- Exportación Excel
"""

# Configuración de columnas disponibles para facturas
INVOICE_COLUMNS = {
    'id': {
        'label': '# Factura',
        'field': 'id',
        'type': 'number',
        'width': 100,
        'visible': True,
        'required': True,  # Columna obligatoria
        'sortable': True,
    },
    'customer': {
        'label': 'Cliente',
        'field': 'customer',
        'type': 'fk',
        'width': 200,
        'visible': True,
        'required': False,
        'sortable': True,
    },
    'customer_dni': {
        'label': 'DNI/RUC Cliente',
        'field': 'customer__dni',
        'type': 'text',
        'width': 130,
        'visible': False,
        'required': False,
        'sortable': True,
    },
    'invoice_date': {
        'label': 'Fecha',
        'field': 'invoice_date',
        'type': 'datetime',
        'width': 150,
        'visible': True,
        'required': False,
        'sortable': True,
    },
    'num_items': {
        'label': 'Productos',
        'field': 'num_items',
        'type': 'computed',
        'width': 100,
        'visible': False,
        'required': False,
        'sortable': False,
    },
    'subtotal': {
        'label': 'Subtotal',
        'field': 'subtotal',
        'type': 'decimal',
        'width': 120,
        'visible': True,
        'required': False,
        'sortable': True,
    },
    'tax': {
        'label': 'Impuesto (IVA)',
        'field': 'tax',
        'type': 'decimal',
        'width': 120,
        'visible': True,
        'required': False,
        'sortable': True,
    },
    'total': {
        'label': 'Total',
        'field': 'total',
        'type': 'decimal',
        'width': 120,
        'visible': True,
        'required': False,
        'sortable': True,
    },
    'is_active': {
        'label': 'Estado',
        'field': 'is_active',
        'type': 'boolean',
        'width': 100,
        'visible': False,
        'required': False,
        'sortable': True,
    },
}

# Configuración por defecto
INVOICE_DEFAULT_VISIBLE_COLUMNS = [col for col, config in INVOICE_COLUMNS.items() if config['visible']]


def get_invoice_visible_columns(visible_list=None):
    """
    Obtener configuración de columnas visibles para facturas.
    """
    if visible_list is None:
        visible_list = INVOICE_DEFAULT_VISIBLE_COLUMNS

    result = {}
    for col in visible_list:
        if col in INVOICE_COLUMNS:
            result[col] = INVOICE_COLUMNS[col]

    if not result and 'id' in INVOICE_COLUMNS:
        result['id'] = INVOICE_COLUMNS['id']

    return result


def get_all_invoice_columns():
    """Retorna todas las columnas disponibles para facturas."""
    return INVOICE_COLUMNS


def validate_invoice_visible_columns(visible_list):
    """
    Validar que la lista de columnas visibles sea válida.
    Returns:
        Tupla (es_valida, columnas_validadas)
    """
    if not visible_list:
        return True, INVOICE_DEFAULT_VISIBLE_COLUMNS

    valid_columns = [col for col in visible_list if col in INVOICE_COLUMNS]

    if not valid_columns:
        valid_columns = INVOICE_DEFAULT_VISIBLE_COLUMNS

    return True, valid_columns
