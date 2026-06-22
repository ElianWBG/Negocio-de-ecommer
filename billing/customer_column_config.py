"""
Configuración centralizada de columnas disponibles para el módulo de clientes.
Esta configuración se utiliza en:
- Listado de clientes (customer_list.html)
- Exportación PDF
- Exportación Excel
"""

# Configuración de columnas disponibles para clientes
CUSTOMER_COLUMNS = {
    'dni': {
        'label': 'DNI / RUC',
        'field': 'dni',
        'type': 'text',
        'width': 130,
        'visible': True,
        'required': True,  # Columna obligatoria
        'sortable': True,
    },
    'last_name': {
        'label': 'Apellido',
        'field': 'last_name',
        'type': 'text',
        'width': 150,
        'visible': True,
        'required': False,
        'sortable': True,
    },
    'first_name': {
        'label': 'Nombre',
        'field': 'first_name',
        'type': 'text',
        'width': 150,
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
    'is_active': {
        'label': 'Estado',
        'field': 'is_active',
        'type': 'boolean',
        'width': 100,
        'visible': True,
        'required': False,
        'sortable': True,
    },
    'taxpayer_type': {
        'label': 'Contribuyente',
        'field': 'taxpayer_type',
        'type': 'profile',
        'width': 140,
        'visible': False,
        'required': False,
        'sortable': False,
    },
    'payment_terms': {
        'label': 'Condición de pago',
        'field': 'payment_terms',
        'type': 'profile',
        'width': 140,
        'visible': False,
        'required': False,
        'sortable': False,
    },
    'credit_limit': {
        'label': 'Límite de crédito',
        'field': 'credit_limit',
        'type': 'profile_decimal',
        'width': 130,
        'visible': False,
        'required': False,
        'sortable': False,
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

# Configuración por defecto
CUSTOMER_DEFAULT_VISIBLE_COLUMNS = [col for col, config in CUSTOMER_COLUMNS.items() if config['visible']]


def get_customer_visible_columns(visible_list=None):
    """
    Obtener configuración de columnas visibles para clientes.
    """
    if visible_list is None:
        visible_list = CUSTOMER_DEFAULT_VISIBLE_COLUMNS

    result = {}
    for col in visible_list:
        if col in CUSTOMER_COLUMNS:
            result[col] = CUSTOMER_COLUMNS[col]

    if not result and 'dni' in CUSTOMER_COLUMNS:
        result['dni'] = CUSTOMER_COLUMNS['dni']

    return result


def get_all_customer_columns():
    """Retorna todas las columnas disponibles para clientes."""
    return CUSTOMER_COLUMNS


def validate_customer_visible_columns(visible_list):
    """
    Validar que la lista de columnas visibles sea válida.
    Returns:
        Tupla (es_valida, columnas_validadas)
    """
    if not visible_list:
        return True, CUSTOMER_DEFAULT_VISIBLE_COLUMNS

    valid_columns = [col for col in visible_list if col in CUSTOMER_COLUMNS]

    if not valid_columns:
        valid_columns = CUSTOMER_DEFAULT_VISIBLE_COLUMNS

    return True, valid_columns
