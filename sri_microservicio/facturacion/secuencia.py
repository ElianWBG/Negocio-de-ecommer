"""
Secuencial del comprobante. Debe ser atómico para no repetir números.
Implementación simple basada en la BD; en producción conviene un contador
dedicado por (establecimiento, punto_emision) con select_for_update.
"""
from django.db import transaction
from django.db.models import Max

from .models import Factura


@transaction.atomic
def siguiente_secuencial(establecimiento: str, punto_emision: str) -> str:
    ultimo = (
        Factura.objects.select_for_update()
        .filter(establecimiento=establecimiento, punto_emision=punto_emision)
        .aggregate(m=Max("secuencial"))["m"]
    )
    nuevo = (int(ultimo) + 1) if ultimo else 1
    return str(nuevo).zfill(9)
