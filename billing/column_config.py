"""
Configuración centralizada de columnas disponibles para el módulo de productos.
Esta configuración se utiliza en:
- Listado de productos (product_list.html)
- Exportación PDF
- Exportación Excel
"""

# Configuración de columnas disponibles para productos
PRODUCT_COLUMNS = {
    'image': {
        'label': 'Imagen',
        'field': 'image',
        'type': 'image',
        'width': 80,
        'visible': True,
        'required': False,
        'sortable': False,
    },
    'name': {
        'label': 'Nombre',
        'field': 'name',
        'type': 'text',
        'width': 200,
        'visible': True,
        'required': True,  # Columna obligatoria
        'sortable': True,
    },
    'description': {
        'label': 'Descripción',
        'field': 'description',
        'type': 'text',
        'width': 250,
        'visible': False,
        'required': False,
        'sortable': False,
    },
    'brand': {
        'label': 'Marca',
        'field': 'brand',
        'type': 'relation',
        'width': 120,
        'visible': True,
        'required': False,
        'sortable': True,
    },
    'group': {
        'label': 'Grupo',
        'field': 'group',
        'type': 'relation',
        'width': 120,
        'visible': True,
        'required': False,
        'sortable': True,
    },
    'unit_price': {
        'label': 'Precio',
        'field': 'unit_price',
        'type': 'decimal',
        'width': 100,
        'visible': True,
        'required': False,
        'sortable': True,
    },
    'stock': {
        'label': 'Stock',
        'field': 'stock',
        'type': 'number',
        'width': 80,
        'visible': True,
        'required': False,
        'sortable': True,
    },
    'balance': {
        'label': 'Balance',
        'field': 'balance',
        'type': 'decimal',
        'width': 100,
        'visible': True,
        'required': False,
        'sortable': False,
    },
    'suppliers': {
        'label': 'Proveedores',
        'field': 'suppliers',
        'type': 'relation_m2m',
        'width': 200,
        'visible': True,
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

# Configuración por defecto
DEFAULT_VISIBLE_COLUMNS = [col for col, config in PRODUCT_COLUMNS.items() if config['visible']]


def get_visible_columns(visible_list=None):
    """
    Obtener configuración de columnas visibles.
    
    Args:
        visible_list: Lista de columnas visibles (opcional)
        Si es None, retorna la configuración por defecto.
    
    Returns:
        Dict con configuración de columnas visibles
    """
    if visible_list is None:
        visible_list = DEFAULT_VISIBLE_COLUMNS
    
    # Filtrar solo columnas válidas y visibles
    result = {}
    for col in visible_list:
        if col in PRODUCT_COLUMNS:
            result[col] = PRODUCT_COLUMNS[col]
    
    # Si no hay columnas visibles, mostrar al menos la requerida
    if not result and 'name' in PRODUCT_COLUMNS:
        result['name'] = PRODUCT_COLUMNS['name']
    
    return result


def get_all_columns():
    """Retorna todas las columnas disponibles"""
    return PRODUCT_COLUMNS


def validate_visible_columns(visible_list):
    """
    Validar que la lista de columnas visibles sea válida.
    
    Returns:
        Tupla (es_valida, columnas_validadas)
    """
    if not visible_list:
        # Si no hay columnas, usar por defecto
        return True, DEFAULT_VISIBLE_COLUMNS
    
    # Filtrar columnas inválidas
    valid_columns = [col for col in visible_list if col in PRODUCT_COLUMNS]
    
    # Asegurar que haya al menos una columna
    if not valid_columns:
        valid_columns = DEFAULT_VISIBLE_COLUMNS
    
    return True, valid_columns
