"""
Configuración del microservicio de facturación.
Credenciales sensibles se leen de variables de entorno con python-dotenv.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env(key, default=None):
    return os.environ.get(key, default)


def env_bool(key, default=False):
    return str(os.environ.get(key, default)).lower() in ("1", "true", "yes", "on")


# ------------------------------------------------------------------ Django
SECRET_KEY = env("SECRET_KEY", "dev-insecure-key")
DEBUG = env_bool("DEBUG", False)
ALLOWED_HOSTS = [h.strip() for h in env("ALLOWED_HOSTS", "").split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.staticfiles",
    "rest_framework",
    "facturacion",
]

MIDDLEWARE = [
    "django.middleware.common.CommonMiddleware",
    "django.middleware.security.SecurityMiddleware",
]

ROOT_URLCONF = "sri_service.urls"
WSGI_APPLICATION = "sri_service.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

LANGUAGE_CODE = "es-ec"
TIME_ZONE = "America/Guayaquil"
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
}

# ------------------------------------------------------------------ Celery
CELERY_BROKER_URL = env("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 60 * 10
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
# EAGER=True ejecuta las tareas en el mismo proceso (sin Redis/worker).
# Útil para probar el flujo completo en desarrollo.
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_EAGER", False)
CELERY_TASK_EAGER_PROPAGATES = True

# ------------------------------------------------------------------ SRI / Emisor
SRI = {
    "AMBIENTE": env("SRI_AMBIENTE", "1"),          # 1=Pruebas, 2=Producción
    "TIPO_EMISION": env("SRI_TIPO_EMISION", "1"),  # 1=Normal
    "WSDL_RECEPCION": env("SRI_WSDL_RECEPCION"),
    "WSDL_AUTORIZACION": env("SRI_WSDL_AUTORIZACION"),
    # Modo simulado: sin firma real ni conexión al SRI (desarrollo/pruebas).
    "SIMULADO": env_bool("SRI_SIMULADO", True),
}

EMISOR = {
    "RUC": env("EMISOR_RUC"),
    "RAZON_SOCIAL": env("EMISOR_RAZON_SOCIAL"),
    "NOMBRE_COMERCIAL": env("EMISOR_NOMBRE_COMERCIAL"),
    "DIR_MATRIZ": env("EMISOR_DIR_MATRIZ"),
    "DIR_ESTABLECIMIENTO": env("EMISOR_DIR_ESTABLECIMIENTO"),
    "ESTABLECIMIENTO": env("EMISOR_ESTABLECIMIENTO", "001"),
    "PUNTO_EMISION": env("EMISOR_PUNTO_EMISION", "001"),
    "OBLIGADO_CONTABILIDAD": env("EMISOR_OBLIGADO_CONTABILIDAD", "NO"),
    "CONTRIBUYENTE_ESPECIAL": env("EMISOR_CONTRIBUYENTE_ESPECIAL", ""),
}

# ------------------------------------------------------------------ Firma
FIRMA = {
    "P12_PATH": env("FIRMA_P12_PATH"),
    "P12_PASSWORD": env("FIRMA_P12_PASSWORD"),
}

# ------------------------------------------------------------------ Correo
# En modo simulado, el correo se imprime en consola (no requiere SMTP).
if SRI["SIMULADO"]:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", "localhost")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "facturacion@localhost")

# Carpeta donde se guardan XML/PDF generados
COMPROBANTES_DIR = BASE_DIR / env("COMPROBANTES_DIR", "comprobantes")
COMPROBANTES_DIR.mkdir(exist_ok=True)
