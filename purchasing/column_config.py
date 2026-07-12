"""
Configuración centralizada de columnas disponibles para el módulo de compras.
Esta configuración se utiliza en:
- Listado de compras (purchase_list.html)
- Exportación PDF
- Exportación Excel
"""

PURCHASE_COLUMNS = {
    'id': {
        'label': 'N°',
        'field': 'id',
        'type': 'text',
        'width': 60,
        'visible': True,
        'required': True,  # Columna obligatoria
        'sortable': True,
    },
    'supplier': {
        'label': 'Proveedor',
        'field': 'supplier',
        'type': 'text',
        'width': 180,
        'visible': True,
        'required': False,
        'sortable': True,
    },
    'document_number': {
        'label': 'N° documento',
        'field': 'document_number',
        'type': 'text',
        'width': 140,
        'visible': True,
        'required': False,
        'sortable': True,
    },
    'purchase_date': {
        'label': 'Fecha',
        'field': 'purchase_date',
        'type': 'datetime',
        'width': 160,
        'visible': True,
        'required': False,
        'sortable': True,
    },
    'num_items': {
        'label': 'Productos',
        'field': 'num_items',
        'type': 'count',
        'width': 110,
        'visible': True,
        'required': False,
        'sortable': False,
    },
    'subtotal': {
        'label': 'Subtotal',
        'field': 'subtotal',
        'type': 'currency',
        'width': 110,
        'visible': False,
        'required': False,
        'sortable': True,
    },
    'tax': {
        'label': 'IVA (15%)',
        'field': 'tax',
        'type': 'currency',
        'width': 110,
        'visible': False,
        'required': False,
        'sortable': True,
    },
    'total': {
        'label': 'Total',
        'field': 'total',
        'type': 'currency',
        'width': 120,
        'visible': True,
        'required': False,
        'sortable': True,
    },
    'is_active': {
        'label': 'Activo',
        'field': 'is_active',
        'type': 'boolean',
        'width': 100,
        'visible': False,
        'required': False,
        'sortable': True,
    },
    'tipo_pago': {
        'label': 'Tipo de pago',
        'field': 'tipo_pago',
        'type': 'text',
        'width': 110,
        'visible': True,
        'required': False,
        'sortable': True,
    },
    'estado': {
        'label': 'Estado',
        'field': 'estado',
        'type': 'text',
        'width': 110,
        'visible': True,
        'required': False,
        'sortable': True,
    },
    'saldo': {
        'label': 'Saldo',
        'field': 'saldo',
        'type': 'currency',
        'width': 110,
        'visible': False,
        'required': False,
        'sortable': True,
    },
}

PURCHASE_DEFAULT_VISIBLE_COLUMNS = [col for col, config in PURCHASE_COLUMNS.items() if config['visible']]


def get_purchase_visible_columns(visible_list=None):
    """Obtener configuración de columnas visibles para compras."""
    if visible_list is None:
        visible_list = PURCHASE_DEFAULT_VISIBLE_COLUMNS

    result = {}
    for col in visible_list:
        if col in PURCHASE_COLUMNS:
            result[col] = PURCHASE_COLUMNS[col]

    if not result and 'id' in PURCHASE_COLUMNS:
        result['id'] = PURCHASE_COLUMNS['id']

    return result


def get_all_purchase_columns():
    """Retorna todas las columnas disponibles para compras."""
    return PURCHASE_COLUMNS


def validate_purchase_visible_columns(visible_list):
    """
    Validar que la lista de columnas visibles sea válida.
    Returns:
        Tupla (es_valida, columnas_validadas)
    """
    if not visible_list:
        return True, PURCHASE_DEFAULT_VISIBLE_COLUMNS

    valid_columns = [col for col in visible_list if col in PURCHASE_COLUMNS]

    if not valid_columns:
        valid_columns = PURCHASE_DEFAULT_VISIBLE_COLUMNS

    return True, valid_columns
