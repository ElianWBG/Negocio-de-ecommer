# Microservicio de Facturación Electrónica — SRI Ecuador (esquema offline)

Servicio Django + DRF + Celery que recibe una venta del sistema principal,
responde **HTTP 202** y procesa en segundo plano: genera clave de acceso y XML,
firma **XAdES-BES**, envía al SRI (recepción/autorización vía SOAP `zeep`),
genera el **RIDE (PDF)** y envía el correo al cliente.

## Estructura de aplicaciones

```
sri_microservicio/
├── manage.py
├── requirements.txt
├── .env.example
├── sri_service/                 # Proyecto Django
│   ├── __init__.py              # carga la app Celery
│   ├── settings.py              # lee credenciales vía python-dotenv
│   ├── celery.py                # instancia Celery (broker=Redis)
│   ├── urls.py
│   └── wsgi.py
└── facturacion/                 # App principal
    ├── models.py                # modelo Factura + estados
    ├── serializers.py           # DRF: valida el JSON de la venta
    ├── views.py                 # endpoint -> 202 + dispara Celery
    ├── urls.py
    ├── tasks.py                 # tarea Celery orquestadora
    ├── admin.py
    └── sri/                     # lógica de dominio (desacoplada de Django)
        ├── clave_acceso.py      # 49 dígitos + Módulo 11
        ├── xml_builder.py       # XML factura (ElementTree)
        ├── firma.py             # XAdES-BES desde .p12
        ├── ws_sri.py            # cliente SOAP zeep (recepción/autorización)
        ├── ride.py              # PDF (reportlab) + QR
        └── correo.py            # envío de email con adjuntos
```

## Flujo asíncrono

```
POST /api/v1/facturas/  ──►  view valida JSON  ──►  crea Factura(PENDIENTE)
                                             │
                                             ├──►  responde 202 { id, estado }
                                             │
                                             └──►  emitir_factura.delay(factura_id)   (Celery)
                                                        1. clave de acceso + XML
                                                        2. firma XAdES-BES (.p12)
                                                        3. recepción SRI   -> RECIBIDO
                                                        4. autorización SRI -> AUTORIZADO
                                                        5. RIDE (PDF) + QR
                                                        6. correo al cliente
```

## Puesta en marcha

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # completar RUC, ruta .p12, clave, SMTP...
python manage.py migrate

# Terminal 1: Redis (broker)
redis-server

# Terminal 2: worker Celery
celery -A sri_service worker -l info

# Terminal 3: API
python manage.py runserver 0.0.0.0:8001
```

## Modo simulado (desarrollo sin firma real ni SRI)

La factura electrónica real exige un **certificado `.p12`** y conexión a los WS del
SRI. Para desarrollar sin eso, activa el **modo simulado**:

```env
SRI_SIMULADO=True      # firma MOCK + recepción/autorización instantáneas = AUTORIZADO
CELERY_EAGER=True       # ejecuta la tarea inline (sin Redis ni worker)
```

Con esos dos flags puedes probar TODO el flujo con solo `runserver`:

```bash
python manage.py migrate
python manage.py runserver 0.0.0.0:8001

curl -X POST http://localhost:8001/api/v1/facturas/ \
  -H "Content-Type: application/json" \
  -d '{
    "cliente_identificacion": "0102030405",
    "cliente_razon_social": "Juan Perez",
    "cliente_email": "juan@example.com",
    "items": [
      {"codigo": "P001", "descripcion": "Producto A", "cantidad": 2, "precio_unitario": 10.00}
    ]
  }'
# -> 202 { "id": 1, "estado": "PENDIENTE", ... }
# La tarea corre inline: genera clave, XML, firma mock, autoriza, RIDE y "envía"
# el correo por consola. Consulta el estado:
curl http://localhost:8001/api/v1/facturas/1/     # -> estado AUTORIZADO
```

Qué hace la simulación (`facturacion/sri/simulador.py`):
- **Firma**: inserta un `<ds:Signature>` ficticio (no válido ante el SRI).
- **Recepción**: responde `RECIBIDA`.
- **Autorización**: responde `AUTORIZADO` al instante; nº de autorización = clave de acceso.
- **Correo**: backend de consola (no necesita SMTP).

Para producción: `SRI_SIMULADO=False`, configura el `.p12` real y los WSDL, y
levanta Redis + worker Celery.

## Notas de librerías

- **Firma XAdES-BES**: se usa `xmlsig` + `xades` (envoltorios sobre `lxml`/`cryptography`)
  por ser las que mejor cumplen el perfil que exige el SRI. Alternativa: `signxml`.
  El `.p12` se abre con `cryptography.hazmat` (no requiere `pyOpenSSL`).
- **SOAP**: `zeep` con `Transport` y timeouts; el SRI espera el XML firmado en base64.
- **PDF/QR**: `reportlab` + `qrcode`.
- Ambiente SRI: `1` = Pruebas (celcer), `2` = Producción (cel).
