"""
Cliente SOAP del SRI usando `zeep` (esquema offline).

Dos servicios:
  * Recepción   -> recibe el XML firmado (base64). Respuesta: RECIBIDA | DEVUELTA
  * Autorización -> se consulta por clave de acceso. Respuesta: AUTORIZADO | ...

Los WSDL se leen de settings.SRI (Pruebas por defecto).
"""
import base64
import time
from dataclasses import dataclass, field

from django.conf import settings


@dataclass
class ResultadoRecepcion:
    estado: str                       # "RECIBIDA" | "DEVUELTA"
    mensajes: list = field(default_factory=list)
    raw: object = None


@dataclass
class ResultadoAutorizacion:
    estado: str                       # "AUTORIZADO" | "NO AUTORIZADO" | "EN PROCESO"
    numero_autorizacion: str = ""
    fecha_autorizacion: object = None
    comprobante: str = ""             # XML autorizado
    mensajes: list = field(default_factory=list)
    raw: object = None


def _client(wsdl: str):
    # Import perezoso: en modo simulado no se requiere `zeep`.
    from zeep import Client, Settings
    from zeep.transports import Transport

    transport = Transport(timeout=30, operation_timeout=30)
    return Client(wsdl, settings=Settings(strict=False, xml_huge_tree=True), transport=transport)


def _mensajes(comprobante) -> list:
    """Extrae la lista de <mensaje> de una respuesta zeep (objeto -> dicts)."""
    salida = []
    try:
        for c in comprobante.mensajes.mensaje:
            salida.append(
                {
                    "identificador": getattr(c, "identificador", ""),
                    "mensaje": getattr(c, "mensaje", ""),
                    "informacionAdicional": getattr(c, "informacionAdicional", ""),
                    "tipo": getattr(c, "tipo", ""),
                }
            )
    except (AttributeError, TypeError):
        pass
    return salida


def enviar_recepcion(xml_firmado: bytes) -> ResultadoRecepcion:
    """
    Envía el XML firmado al servicio de Recepción.
    El SRI espera el contenido en base64 (parámetro `xml`).
    """
    if settings.SRI.get("SIMULADO"):
        from . import simulador
        return simulador.simular_recepcion(xml_firmado)

    client = _client(settings.SRI["WSDL_RECEPCION"])
    xml_b64 = base64.b64encode(xml_firmado)

    respuesta = client.service.validarComprobante(xml_b64)
    estado = getattr(respuesta, "estado", "DEVUELTA")

    mensajes = []
    try:
        for comp in respuesta.comprobantes.comprobante:
            mensajes.extend(_mensajes(comp))
    except (AttributeError, TypeError):
        pass

    return ResultadoRecepcion(estado=estado, mensajes=mensajes, raw=respuesta)


def consultar_autorizacion(clave_acceso: str) -> ResultadoAutorizacion:
    """Consulta una sola vez el servicio de Autorización por clave de acceso."""
    if settings.SRI.get("SIMULADO"):
        from pathlib import Path

        from . import simulador

        xml_path = Path(settings.COMPROBANTES_DIR) / f"{clave_acceso}.xml"
        xml_firmado = xml_path.read_bytes() if xml_path.exists() else b""
        return simulador.simular_autorizacion(clave_acceso, xml_firmado)

    client = _client(settings.SRI["WSDL_AUTORIZACION"])
    respuesta = client.service.autorizacionComprobante(clave_acceso)

    try:
        aut = respuesta.autorizaciones.autorizacion[0]
    except (AttributeError, IndexError, TypeError):
        return ResultadoAutorizacion(estado="EN PROCESO", raw=respuesta)

    return ResultadoAutorizacion(
        estado=getattr(aut, "estado", "NO AUTORIZADO"),
        numero_autorizacion=getattr(aut, "numeroAutorizacion", "") or "",
        fecha_autorizacion=getattr(aut, "fechaAutorizacion", None),
        comprobante=getattr(aut, "comprobante", "") or "",
        mensajes=_mensajes(aut),
        raw=respuesta,
    )


def esperar_autorizacion(
    clave_acceso: str, *, intentos: int = 6, espera_seg: int = 5
) -> ResultadoAutorizacion:
    """
    Poll de la autorización: el SRI puede tardar en procesar tras la recepción.
    Reintenta hasta `intentos` veces mientras el estado sea 'EN PROCESO'.
    """
    ultimo = ResultadoAutorizacion(estado="EN PROCESO")
    for _ in range(intentos):
        ultimo = consultar_autorizacion(clave_acceso)
        if ultimo.estado != "EN PROCESO":
            return ultimo
        time.sleep(espera_seg)
    return ultimo
