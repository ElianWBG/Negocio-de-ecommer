# Negocio de Ecommerce (SALES_A2)

Plataforma Django de gestión de ventas y tienda online, desarrollada por **ELIAN VLADIMIR GALEAS, JOSE ANTONIO TORRES, JONATHAN BELFOR CASTRO, JHOAN CEVALLOS VILLAVICENCIO, JEAN JIMENEZ BAJAÑA**.

Combina un **panel administrativo** (catálogo, ventas, compras, cobros, pagos, reportes, roles) con una **tienda pública** donde los clientes se registran, arman un carrito, solicitan compras y pagan online.

## Índice

- [Módulos del sistema](#módulos-del-sistema)
- [Roles y permisos](#roles-y-permisos)
- [Listados: filtros, paginación y exportación](#listados-filtros-paginación-y-exportación)
- [Pagos y notificaciones](#pagos-y-notificaciones)
- [Microservicio de facturación SRI (opcional)](#microservicio-de-facturación-sri-opcional)
- [Stack técnico](#stack-técnico)
- [Cómo ejecutar el proyecto](#cómo-ejecutar-el-proyecto)
- [Variables de entorno](#variables-de-entorno)
- [Despliegue](#despliegue)
- [Estructura del repositorio](#estructura-del-repositorio)

## Módulos del sistema

| App | Responsabilidad |
|-----|------------------|
| `billing` | Catálogo (marcas, grupos, productos, proveedores), clientes, facturación, configuración del negocio, gestión de usuarios, registro de actividad (auditoría) y reportes de ventas/stock. |
| `purchasing` | Compras a proveedores (contado y crédito). |
| `cobros` | Cuentas por cobrar: pagos parciales sobre facturas a crédito. |
| `pagos` | Cuentas por pagar: pagos parciales sobre compras a crédito. |
| `reportes` | Panel con cuentas por cobrar/pagar, ventas por periodo, productos más vendidos y stock bajo. |
| `security` | Roles (grupos de Django) y traducción de permisos a español. |
| `storefront` | Tienda pública: registro/login de clientes con verificación por email, catálogo, carrito, checkout, pagos (PayPhone, PayPal o transferencia manual) y panel de solicitudes de compra. |
| `shared` | Utilidades comunes: exportación a columnas, mixins, decoradores, validadores. |
| `sri_microservicio` | Microservicio Django+DRF+Celery independiente para facturación electrónica real ante el SRI (Ecuador). Ver [sección dedicada](#microservicio-de-facturación-sri-opcional). |

### Facturación

- Ventas al contado o a crédito (`tipo_pago`, `saldo`, `estado` en `Invoice`/`Purchase`).
- PDF de factura con formato **RIDE** del SRI (`billing/xml_utils.py` genera además un XML inspirado en el esquema del SRI, con fines educativos — no es una factura electrónica válida ante el SRI real; para eso existe el microservicio aparte).
- Reenvío de factura (PDF + XML adjuntos) por correo.
- Campo **RUC del negocio** en `ConfigNegocio` para el emisor de la factura.

### Cuentas por cobrar / pagar (`cobros`, `pagos`)

- Listado de facturas/compras a crédito pendientes.
- Registrar, editar y eliminar pagos parciales, recalculando el saldo automáticamente.
- Reglas de negocio: no se permite pagar de más, pagos negativos o en cero, ni pagar documentos anulados; todo dentro de `transaction.atomic()`.

## Roles y permisos

Los roles se crean/actualizan con `python manage.py setup_roles` (definidos en `security/management/commands/setup_roles_full.py`):

| Rol | Acceso |
|-----|--------|
| **Administrador** | Todos los permisos del sistema. |
| **Vendedor** | Clientes, facturas y aprobación/rechazo de pedidos de la tienda. |
| **Analista de Compras** | Catálogo completo (marcas, grupos, proveedores, productos) y compras a proveedores. |
| **Contador** | Cuentas por cobrar/pagar y reportes financieros (solo lectura del resto). |
| **Atención al Cliente** | Revisar y aprobar/rechazar pedidos de la tienda. |

Cada vista del panel valida permisos reales de Django (no solo el rol visual), y `security/permission_labels.py` traduce los permisos (`Can view Marca` → `Ver marca`) para la UI de gestión de usuarios sin tocar los nombres en base de datos.

## Listados: filtros, paginación y exportación

### Búsqueda y filtros por columna

Los listados (productos, clientes, facturas, etc.) permiten filtrar por cada columna, con el control adecuado según el tipo de dato:

| Columna     | Control                        |
|-------------|--------------------------------|
| Nombre      | Texto (búsqueda parcial)       |
| Marca       | Lista desplegable              |
| Grupo       | Lista desplegable              |
| Proveedor   | Lista desplegable              |
| Estado      | Lista (Todos / Activo / Inactivo) |
| Precio      | Rango numérico (mín / máx)     |
| Stock       | Rango numérico (mín / máx)     |

Los botones **Buscar** y **Limpiar** aplican o reinician los filtros. Cada listado también permite elegir qué columnas mostrar (persistido vía los endpoints `.../api/update-visible-columns/`).

### Paginación

Los resultados se paginan (`paginate_by` en la vista). La navegación conserva los filtros activos al cambiar de página.

### Exportación a PDF y Excel

Cada listado puede exportar **los registros filtrados** (no solo la página actual) mediante los botones **Listado PDF** y **Listado Excel**.

La lógica está centralizada en un mixin genérico reutilizable: [`ExportListMixin`](shared/export_mixins.py). Para habilitar la exportación en cualquier `ListView` basta con heredar del mixin y declarar las columnas:

```python
from shared.export_mixins import ExportListMixin

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

## Pagos y notificaciones

- **PayPhone**: botón de pago con tarjeta (`storefront/payphone.py`), requiere `PAYPHONE_TOKEN` y `PAYPHONE_STORE_ID`.
- **PayPal**: creación y captura de orden vía API (`PAYPAL_CLIENT_ID` / `PAYPAL_SECRET`).
- **Transferencia/pago manual**: el cliente sube comprobante y un vendedor confirma.
- **Email**: en desarrollo usa el backend de consola; en producción se usa **SendGrid** como único proveedor (`SENDGRID_API_KEY`), para verificación de cuenta de clientes, confirmación de pedidos, envío de facturas y promociones masivas.
- Notificación al proveedor (`ADMIN_NOTIFICATION_EMAIL`) cuando llega una solicitud de compra nueva.

## Microservicio de facturación SRI (opcional)

`sri_microservicio/` es un servicio **independiente** (Django + DRF + Celery + Redis) que sí implementa facturación electrónica real ante el SRI Ecuador: genera la clave de acceso (módulo 11), firma XAdES-BES con un certificado `.p12`, envía la factura por SOAP (recepción/autorización), genera el RIDE en PDF con QR y envía el correo al cliente. No está conectado automáticamente al proyecto principal — es un componente aparte pensado para integrarse cuando se necesite facturación electrónica válida. Tiene su propio `README.md`, `requirements.txt` y modo simulado (`SRI_SIMULADO=True`) para probar el flujo completo sin certificado ni Redis. Ver [`sri_microservicio/README.md`](sri_microservicio/README.md).

## Stack técnico

- **Django 6.0.6** + `django-extensions`, `django-widget-tweaks`
- **PostgreSQL** vía `django-environ` (`DATABASE_URL`) y `psycopg[binary]`
- **Cloudinary** para almacenamiento de imágenes en producción (local usa filesystem)
- **WhiteNoise** para archivos estáticos + **Gunicorn** como servidor de producción
- **openpyxl** / **reportlab** para exportación a Excel/PDF y generación de facturas PDF
- **SendGrid** para envío de correo transaccional
- **PayPhone** / **PayPal** para pagos online
- Base de datos de desarrollo incluida como `db.sqlite3` (el proyecto está preparado para Postgres vía `DATABASE_URL`, ver `.env.example`)

## Cómo ejecutar el proyecto

### 1. Crear el entorno virtual

```cmd
py -m venv ent_sales_A2
```

> Si `py` no funciona, usa `python` en su lugar.

### 2. Activar el entorno virtual

```cmd
ent_sales_A2\Scripts\activate.bat
```

### 3. Instalar las dependencias

```cmd
pip install -r requirements.txt
```

### 4. Configurar las variables de entorno

```cmd
copy .env.example .env
```

Rellena `.env` con tus valores (ver [Variables de entorno](#variables-de-entorno)). También puedes usar `python crear_env.py` como ayuda para generarlo.

### 5. Aplicar las migraciones

```cmd
ent_sales_A2\Scripts\python.exe manage.py migrate
```

### 6. Crear los roles del sistema

```cmd
ent_sales_A2\Scripts\python.exe manage.py setup_roles
```

### 7. (Opcional) Cargar datos de demostración

```cmd
ent_sales_A2\Scripts\python.exe seed_demo.py
ent_sales_A2\Scripts\python.exe seed_images.py
```

### 8. Ejecutar el servidor

```cmd
ent_sales_A2\Scripts\python.exe manage.py runserver
```

Abre el navegador en: http://127.0.0.1:8000 (tienda pública) o http://127.0.0.1:8000/panel/ (panel administrativo, requiere login de staff).

## Variables de entorno

Definidas en `.env` (ver `.env.example` completo):

| Variable | Uso |
|----------|-----|
| `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | Configuración base de Django. |
| `DATABASE_URL` | Conexión Postgres, formato `postgres://usuario:password@host:puerto/bd`. |
| `PAYPHONE_TOKEN`, `PAYPHONE_STORE_ID` | Botón de pago con tarjeta. |
| `PAYPAL_CLIENT_ID`, `PAYPAL_SECRET` | Pagos con PayPal. |
| `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL` | Envío de correo (consola en local, SMTP en producción). |
| `SENDGRID_API_KEY` | Envío de correo vía SendGrid (proveedor usado en producción). |
| `ADMIN_NOTIFICATION_EMAIL` | Correo que recibe alertas de pedidos nuevos. |
| `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` | Almacenamiento de imágenes en producción. |

## Despliegue

Preparado para **Railway** (`railway.toml`) y compatible con cualquier plataforma que soporte `Procfile` (Heroku-style):

```
web: gunicorn config.wsgi --log-file -
```

El comando de arranque en Railway ejecuta, en orden: `collectstatic`, `migrate`, `setup_roles` y luego levanta `gunicorn`.

## Estructura del repositorio

```
├── billing/            # Catálogo, clientes, facturación, config del negocio, usuarios, auditoría
├── purchasing/          # Compras a proveedores
├── cobros/               # Cuentas por cobrar
├── pagos/                # Cuentas por pagar
├── reportes/             # Panel de reportes
├── security/             # Roles y permisos
├── storefront/           # Tienda pública (catálogo, carrito, checkout, pagos)
├── shared/                # Utilidades comunes (exportación, mixins, validadores)
├── sri_microservicio/     # Microservicio independiente de facturación electrónica SRI
├── templates/             # Plantillas base compartidas
├── config/                # Settings, URLs raíz, WSGI/ASGI
├── manage.py
├── requirements.txt
├── railway.toml / Procfile
└── .env.example
```
