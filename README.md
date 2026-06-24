# SALES_A2

Proyecto Django para gestión de ventas.

## Funcionalidade

Gestión de marcas, grupos, proveedores, productos, clientes y facturas. Además, el listado de **Productos** incluye:

### Búsqueda y filtros por columna

El listado de productos permite filtrar por cada columna de la consulta, con el control adecuado según el tipo de dato:

| Columna     | Control                        |
|-------------|--------------------------------|
| Nombre      | Texto (búsqueda parcial)       |
| Marca       | Lista desplegable              |
| Grupo       | Lista desplegable              |
| Proveedor   | Lista desplegable              |
| Estado      | Lista (Todos / Activo / Inactivo) |
| Precio      | Rango numérico (mín / máx)     |
| Stock       | Rango numérico (mín / máx)     |

Los botones **Buscar** y **Limpiar** aplican o reinician los filtros.

### Paginación

Los resultados se paginan (configurable con `paginate_by` en la vista). La navegación conserva los filtros activos al cambiar de página.

### Exportación a PDF y Excel

Cada listado puede exportar **los registros filtrados** (no solo la página actual) mediante los botones **Listado PDF** y **Listado Excel**.

La lógica está centralizada en un mixin genérico reutilizable: [`ExportListMixin`](Sales_A2/billing/mixins.py). Para habilitar la exportación en cualquier `ListView` basta con heredar del mixin y declarar las columnas:

```python
from .mixins import ExportListMixin

class ProductListView(ExportListMixin, LoginRequiredMixin, ListView):
    export_title = 'Productos'
    export_fields = [
        ('Nombre', 'name'),                 # atributo simple
        ('Marca', 'brand.name'),            # atributo anidado
        ('Precio', lambda o: f'{o.unit_price:.2f}'),  # callable
        ('Estado', lambda o: 'Activo' if o.is_active else 'Inactivo'),
    ]
```

Luego se añaden los botones en la plantilla apuntando a `?<filtros>&export=pdf` o `?<filtros>&export=excel`.

> Requiere las dependencias `openpyxl` (Excel) y `reportlab` (PDF), incluidas en `requirements.txt`.

## Cómo ejecutar el proyecto

### 1. Clonar el repositorio

```cmd
git clone https://github.com/Jonathan1700/SALES_A2.git
cd SALES_A2/Sales_A2
```

### 2. Crear el entorno virtual

```cmd
py -m venv ent_sales_A2
```

> Si `py` no funciona, usa `python` en su lugar.

### 3. Activar el entorno virtual

```cmd
ent_sales_A2\Scripts\activate.bat
```

### 4. Instalar las dependencias

```cmd
pip install -r requirements.txt
```

### 5. Aplicar las migraciones

```cmd
ent_sales_A2\Scripts\python.exe manage.py migrate
```

### 6. Ejecutar el servidor

```cmd
ent_sales_A2\Scripts\python.exe manage.py runserver
```


