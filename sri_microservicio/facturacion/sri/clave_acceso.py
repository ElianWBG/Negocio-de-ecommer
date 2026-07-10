"""
Clave de Acceso del SRI — 49 dígitos.

Estructura (48 dígitos + 1 verificador):
    ddmmaaaa   (8)  fecha de emisión
    cc         (2)  tipo de comprobante (01=factura)
    ruc        (13) RUC del emisor
    a          (1)  ambiente (1=pruebas, 2=producción)
    serie      (6)  establecimiento(3) + punto de emisión(3)
    secuencial (9)
    codigo     (8)  código numérico (aleatorio/propio)
    e          (1)  tipo de emisión (1=normal)
    dv         (1)  dígito verificador (Módulo 11)
"""
import random
from datetime import date


def modulo11(cadena48: str) -> int:
    """
    Dígito verificador Módulo 11 con pesos 2..7 cíclicos, de derecha a izquierda.
    Reglas del SRI: si el resultado es 11 -> 0; si es 10 -> 1.
    """
    pesos = [2, 3, 4, 5, 6, 7]
    total = 0
    for i, digito in enumerate(reversed(cadena48)):
        peso = pesos[i % len(pesos)]
        total += int(digito) * peso

    residuo = total % 11
    verificador = 11 - residuo
    if verificador == 11:
        return 0
    if verificador == 10:
        return 1
    return verificador


def generar_clave_acceso(
    *,
    fecha_emision: date,
    tipo_comprobante: str,   # "01" factura
    ruc: str,
    ambiente: str,           # "1" | "2"
    establecimiento: str,    # "001"
    punto_emision: str,      # "001"
    secuencial: str,         # "000000123"
    tipo_emision: str = "1",
    codigo_numerico: str | None = None,
) -> str:
    if codigo_numerico is None:
        codigo_numerico = str(random.randint(0, 99_999_999)).zfill(8)

    serie = f"{establecimiento}{punto_emision}"  # 6 dígitos
    cuerpo = (
        f"{fecha_emision.strftime('%d%m%Y')}"
        f"{tipo_comprobante}"
        f"{ruc}"
        f"{ambiente}"
        f"{serie}"
        f"{secuencial.zfill(9)}"
        f"{codigo_numerico.zfill(8)}"
        f"{tipo_emision}"
    )
    if len(cuerpo) != 48:
        raise ValueError(f"Cuerpo de la clave debe tener 48 dígitos, tiene {len(cuerpo)}")

    dv = modulo11(cuerpo)
    return f"{cuerpo}{dv}"
