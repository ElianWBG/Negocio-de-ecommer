"""Envío del correo al cliente con el XML autorizado y el RIDE (PDF) adjuntos."""
from pathlib import Path

from django.core.mail import EmailMessage


def enviar_comprobante(*, factura, xml_path: str | Path, pdf_path: str | Path) -> None:
    if not factura.cliente_email:
        return

    asunto = f"Factura electrónica {factura.numero_comprobante}"
    cuerpo = (
        f"Estimado/a {factura.cliente_razon_social},\n\n"
        f"Adjuntamos su factura electrónica autorizada por el SRI.\n"
        f"Número: {factura.numero_comprobante}\n"
        f"Clave de acceso: {factura.clave_acceso}\n"
        f"Autorización: {factura.numero_autorizacion}\n\n"
        f"Gracias por su compra."
    )

    email = EmailMessage(
        subject=asunto,
        body=cuerpo,
        to=[factura.cliente_email],
    )
    if xml_path and Path(xml_path).exists():
        email.attach_file(str(xml_path))
    if pdf_path and Path(pdf_path).exists():
        email.attach_file(str(pdf_path))

    email.send(fail_silently=False)
