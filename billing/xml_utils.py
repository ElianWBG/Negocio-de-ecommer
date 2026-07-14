"""
Generación de factura en formato XML.

IMPORTANTE: Este XML tiene una estructura INSPIRADA en el esquema de
comprobantes electrónicos del SRI (Ecuador) — nodos como <infoTributaria>,
<infoFactura> y <detalles> — únicamente para que el documento se vea
profesional y sea fácil de leer/parsear. NO es una factura electrónica
válida ante el SRI: le falta la firma electrónica (XAdES-BES), la clave
de acceso real con dígito verificador módulo 11, y la autorización vía
el webservice de recepción/autorización del SRI. Sirve solo para
propósitos educativos / de prueba de este proyecto.
"""
import xml.etree.ElementTree as ET
from xml.dom import minidom
from django.conf import settings


def generate_invoice_xml(invoice) -> bytes:
    """Genera el XML de una factura (billing.models.Invoice) y devuelve
    los bytes ya formateados (pretty-printed, UTF-8) listos para adjuntar
    a un correo o guardar en disco.
    """
    from billing.models import ConfigNegocio

    config = ConfigNegocio.objects.first()
    razon_social = (
        (config.razon_social if config else None)
        or (config.nombre_tienda if config else None)
        or getattr(settings, 'DEFAULT_STORE_NAME', 'Mi Tienda')
    )
    nombre_comercial = (
        (config.nombre_comercial if config else None)
        or razon_social
    )

    customer = invoice.customer

    root = ET.Element('factura', {'id': f'comprobante_{invoice.pk}', 'version': '1.0-demo'})

    # --- infoTributaria: datos del emisor (tienda) ---
    info_tributaria = ET.SubElement(root, 'infoTributaria')
    ET.SubElement(info_tributaria, 'ambiente').text = getattr(config, 'ambiente_sri', '1') or '1'
    ET.SubElement(info_tributaria, 'razonSocial').text = razon_social
    ET.SubElement(info_tributaria, 'nombreComercial').text = nombre_comercial
    ET.SubElement(info_tributaria, 'ruc').text = getattr(config, 'ruc', '') or 'N/A'
    ET.SubElement(info_tributaria, 'codEstablecimiento').text = getattr(config, 'codigo_establecimiento', '001') or '001'
    ET.SubElement(info_tributaria, 'ptoEmi').text = getattr(config, 'punto_emision', '001') or '001'
    ET.SubElement(info_tributaria, 'obligadoContabilidad').text = 'SI' if getattr(config, 'obligado_contabilidad', False) else 'NO'
    ET.SubElement(info_tributaria, 'contribuyenteEspecial').text = getattr(config, 'contribuyente_especial', '') or ''
    ET.SubElement(info_tributaria, 'direccion').text = (config.direccion if config else '') or ''
    ET.SubElement(info_tributaria, 'telefono').text = (config.telefono if config else '') or ''
    ET.SubElement(info_tributaria, 'email').text = (config.email_contacto if config else '') or ''

    # --- infoFactura: cabecera del comprobante ---
    info_factura = ET.SubElement(root, 'infoFactura')
    ET.SubElement(info_factura, 'numeroFactura').text = f'{invoice.pk:09d}'
    ET.SubElement(info_factura, 'fechaEmision').text = invoice.invoice_date.strftime('%Y-%m-%d %H:%M:%S')
    ET.SubElement(info_factura, 'tipoPago').text = invoice.get_tipo_pago_display()
    ET.SubElement(info_factura, 'estado').text = invoice.get_estado_display()

    razon_social_comprador = ET.SubElement(info_factura, 'razonSocialComprador')
    razon_social_comprador.text = customer.full_name
    ET.SubElement(info_factura, 'identificacionComprador').text = customer.dni
    ET.SubElement(info_factura, 'direccionComprador').text = customer.address or ''
    ET.SubElement(info_factura, 'emailComprador').text = customer.email or ''
    ET.SubElement(info_factura, 'telefonoComprador').text = customer.phone or ''

    ET.SubElement(info_factura, 'totalSinImpuestos').text = str(invoice.subtotal)
    ET.SubElement(info_factura, 'totalImpuesto').text = str(invoice.tax)
    ET.SubElement(info_factura, 'importeTotal').text = str(invoice.total)
    ET.SubElement(info_factura, 'saldoPendiente').text = str(invoice.saldo)

    # --- detalles: líneas de la factura ---
    detalles = ET.SubElement(root, 'detalles')
    for detail in invoice.details.select_related('product'):
        detalle = ET.SubElement(detalles, 'detalle')
        ET.SubElement(detalle, 'codigoPrincipal').text = str(detail.product_id)
        ET.SubElement(detalle, 'descripcion').text = detail.product.name
        ET.SubElement(detalle, 'cantidad').text = str(detail.quantity)
        ET.SubElement(detalle, 'precioUnitario').text = str(detail.unit_price)
        ET.SubElement(detalle, 'precioTotalSinImpuesto').text = str(detail.subtotal)

    # Pretty-print con minidom (ElementTree solo no formatea bonito)
    rough_string = ET.tostring(root, encoding='utf-8')
    reparsed = minidom.parseString(rough_string)
    pretty_xml = reparsed.toprettyxml(indent='  ', encoding='utf-8')
    return pretty_xml


def invoice_xml_filename(invoice) -> str:
    return f'factura_{invoice.pk:09d}.xml'
