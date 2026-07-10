"""
Simulador del SRI para desarrollo/pruebas SIN firma electrónica real
ni conexión a los Web Services del SRI.

Activar con SRI_SIMULADO=True (settings.SRI["SIMULADO"]).

Reproduce el "happy path" del esquema offline:
    recepción -> RECIBIDA    ·    autorización -> AUTORIZADO (inmediato)

El número de autorización en el esquema offline es la propia clave de acceso.
"""
from datetime import datetime

from .ws_sri import ResultadoAutorizacion, ResultadoRecepcion


def simular_recepcion(xml_firmado: bytes) -> ResultadoRecepcion:
    return ResultadoRecepcion(
        estado="RECIBIDA",
        mensajes=[{"tipo": "SIMULADO", "mensaje": "Recepción simulada OK"}],
        raw=None,
    )


def simular_autorizacion(clave_acceso: str, xml_firmado: bytes) -> ResultadoAutorizacion:
    ahora = datetime.now()
    comprobante = xml_firmado.decode("utf-8", errors="ignore")
    xml_autorizado = (
        '<autorizacion>'
        f'<estado>AUTORIZADO</estado>'
        f'<numeroAutorizacion>{clave_acceso}</numeroAutorizacion>'
        f'<fechaAutorizacion>{ahora.isoformat()}</fechaAutorizacion>'
        f'<ambiente>PRUEBAS</ambiente>'
        f'<comprobante><![CDATA[{comprobante}]]></comprobante>'
        '</autorizacion>'
    )
    return ResultadoAutorizacion(
        estado="AUTORIZADO",
        numero_autorizacion=clave_acceso,
        fecha_autorizacion=ahora,
        comprobante=xml_autorizado,
        mensajes=[{"tipo": "SIMULADO", "mensaje": "Autorización simulada OK"}],
        raw=None,
    )
