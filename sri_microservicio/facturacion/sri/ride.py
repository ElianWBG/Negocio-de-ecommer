"""
Generación del RIDE (Representación Impresa del Documento Electrónico) en PDF
con reportlab, incluyendo el QR con la clave de acceso.
"""
import io
from pathlib import Path

import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


def _qr_image(texto: str) -> ImageReader:
    qr = qrcode.QRCode(box_size=4, border=1)
    qr.add_data(texto)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf)


def generar_ride(*, emisor: dict, factura, items: list[dict], destino: Path) -> Path:
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(str(destino), pagesize=A4)
    w, h = A4
    y = h - 20 * mm

    # ---- Encabezado emisor ----
    c.setFont("Helvetica-Bold", 14)
    c.drawString(20 * mm, y, emisor["RAZON_SOCIAL"])
    c.setFont("Helvetica", 9)
    c.drawString(20 * mm, y - 6 * mm, f"RUC: {emisor['RUC']}")
    c.drawString(20 * mm, y - 11 * mm, emisor["DIR_MATRIZ"])

    # ---- Recuadro comprobante + QR ----
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(w - 20 * mm, y, "FACTURA")
    c.setFont("Helvetica", 8)
    c.drawRightString(w - 20 * mm, y - 6 * mm, f"No. {factura.numero_comprobante}")
    c.drawRightString(w - 20 * mm, y - 11 * mm, f"Ambiente: {factura.ambiente}")

    if factura.clave_acceso:
        c.drawImage(
            _qr_image(factura.clave_acceso),
            w - 45 * mm, y - 40 * mm, width=25 * mm, height=25 * mm,
        )
        c.setFont("Helvetica", 6)
        c.drawRightString(w - 20 * mm, y - 43 * mm, "Clave de acceso:")
        c.drawRightString(w - 20 * mm, y - 46 * mm, factura.clave_acceso)

    if factura.numero_autorizacion:
        c.setFont("Helvetica", 7)
        c.drawString(20 * mm, y - 20 * mm, f"Autorización: {factura.numero_autorizacion}")

    # ---- Datos del cliente ----
    y -= 55 * mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(20 * mm, y, "Cliente")
    c.setFont("Helvetica", 8)
    c.drawString(20 * mm, y - 5 * mm, f"{factura.cliente_razon_social}")
    c.drawString(20 * mm, y - 10 * mm, f"ID: {factura.cliente_identificacion}")

    # ---- Tabla de ítems ----
    y -= 20 * mm
    c.setFillColor(colors.HexColor("#1E293B"))
    c.rect(20 * mm, y, w - 40 * mm, 7 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(22 * mm, y + 2 * mm, "Cant.")
    c.drawString(40 * mm, y + 2 * mm, "Descripción")
    c.drawRightString(w - 45 * mm, y + 2 * mm, "P. Unit.")
    c.drawRightString(w - 22 * mm, y + 2 * mm, "Total")

    c.setFillColor(colors.black)
    c.setFont("Helvetica", 8)
    y -= 6 * mm
    for it in items:
        total_linea = float(it["cantidad"]) * float(it["precio_unitario"])
        c.drawString(22 * mm, y, f"{it['cantidad']}")
        c.drawString(40 * mm, y, str(it["descripcion"])[:45])
        c.drawRightString(w - 45 * mm, y, f"{float(it['precio_unitario']):.2f}")
        c.drawRightString(w - 22 * mm, y, f"{total_linea:.2f}")
        y -= 6 * mm

    # ---- Totales ----
    y -= 4 * mm
    c.setFont("Helvetica", 9)
    c.drawRightString(w - 45 * mm, y, "Subtotal:")
    c.drawRightString(w - 22 * mm, y, f"{factura.subtotal:.2f}")
    c.drawRightString(w - 45 * mm, y - 5 * mm, "IVA:")
    c.drawRightString(w - 22 * mm, y - 5 * mm, f"{factura.iva:.2f}")
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(w - 45 * mm, y - 11 * mm, "TOTAL:")
    c.drawRightString(w - 22 * mm, y - 11 * mm, f"{factura.total:.2f}")

    c.showPage()
    c.save()
    return destino
