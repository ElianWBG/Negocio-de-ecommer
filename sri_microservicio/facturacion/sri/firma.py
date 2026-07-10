"""
Firma electrónica XAdES-BES del XML de la factura.

El SRI exige un XAdES-BES *enveloped* con referencias específicas (al comprobante,
a los KeyInfo y SignedProperties). Aquí se usa `xmlsig` + `xades`, que se apoyan
en `lxml` y `cryptography`. El certificado se lee de un archivo .p12 cuya ruta y
clave provienen de variables de entorno (settings.FIRMA).

Alternativa válida: `signxml` (SignatureConfiguration con XAdES). Se deja `xmlsig`
por ajustarse mejor al perfil que valida el SRI.
"""
def firmar_comprobante(
    xml_bytes: bytes, *, simulado: bool, p12_path: str = "", p12_password: str = ""
) -> bytes:
    """
    Dispatcher de firma.
      - simulado=True  -> firma MOCK (no requiere .p12). Para desarrollo.
      - simulado=False -> firma XAdES-BES real con el .p12.
    """
    if simulado:
        return _firma_simulada(xml_bytes)
    return firmar_xml_xades_bes(
        xml_bytes, p12_path=p12_path, p12_password=p12_password
    )


def _firma_simulada(xml_bytes: bytes) -> bytes:
    """
    Inserta un nodo <ds:Signature> ficticio antes de </factura> para que el
    comprobante quede 'firmado' de forma verosímil, sin certificado real.
    NO es válido ante el SRI; solo para pruebas locales.
    """
    stub = (
        b'<ds:Signature xmlns:ds="http://www.w3.org/2000/09/xmldsig#" Id="SimulacionBES">'
        b'<ds:SignedInfo><ds:SignatureValue>FIRMA_SIMULADA</ds:SignatureValue></ds:SignedInfo>'
        b'</ds:Signature>'
    )
    if b"</factura>" in xml_bytes:
        return xml_bytes.replace(b"</factura>", stub + b"</factura>")
    return xml_bytes + stub


def _cargar_p12(p12_path: str, password: str):
    """Devuelve (private_key, cert, additional_certs) desde el .p12."""
    from cryptography.hazmat.primitives.serialization import pkcs12

    with open(p12_path, "rb") as fh:
        data = fh.read()
    key, cert, extra = pkcs12.load_key_and_certificates(
        data, password.encode("utf-8")
    )
    return key, cert, extra or []


def firmar_xml_xades_bes(xml_bytes: bytes, *, p12_path: str, p12_password: str) -> bytes:
    """
    Aplica XAdES-BES enveloped sobre `xml_bytes` y devuelve el XML firmado.

    Nota de implementación: `xmlsig`/`xades` construyen el nodo <ds:Signature>
    con las propiedades firmadas (SignedProperties) requeridas por XAdES-BES.
    """
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        NoEncryption,
        PrivateFormat,
    )
    from lxml import etree
    import xmlsig
    import xades

    root = etree.fromstring(xml_bytes)

    # Plantilla de la firma (RSA-SHA1 + C14N, tal como acepta el SRI).
    signature = xmlsig.template.create(
        c14n_method=xmlsig.constants.TransformInclC14N,
        sign_method=xmlsig.constants.TransformRsaSha1,
        name="Signature",
    )
    root.append(signature)

    # Referencia al comprobante (enveloped) + transformada.
    ref = xmlsig.template.add_reference(
        signature, xmlsig.constants.TransformSha1, uri="#comprobante"
    )
    xmlsig.template.add_transform(ref, xmlsig.constants.TransformEnveloped)

    # Referencias a KeyInfo y a las SignedProperties (perfil XAdES).
    xmlsig.template.add_reference(
        signature, xmlsig.constants.TransformSha1, uri="", name="KeyInfo"
    )
    ki = xmlsig.template.ensure_key_info(signature)
    x509 = xmlsig.template.add_x509_data(ki)
    xmlsig.template.x509_data_add_certificate(x509)

    # Propiedades XAdES-BES (SignedProperties, firmante, política vacía = BES).
    qualifying = xades.template.create_qualifying_properties(signature)
    props = xades.template.create_signed_properties(qualifying, name="SignedProperties")
    xades.template.add_claimed_role(props, "Emisor")

    # Contexto de firma con la clave/cert del .p12.
    ctx = xmlsig.SignatureContext()
    key, cert, _ = _cargar_p12(p12_path, p12_password)

    # xmlsig espera la clave/cert en PEM.
    key_pem = key.private_bytes(
        Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption()
    )
    cert_pem = cert.public_bytes(Encoding.PEM)
    ctx.load_pkcs12 = None  # documentar: usamos PEM directo
    ctx.x509 = cert
    ctx.private_key = key

    policy = xades.policy.GenericPolicyId(
        "", "XAdES-BES", xmlsig.constants.TransformSha1
    )
    ctx.sign(signature)  # firma la referencia principal
    policy.calculate_certificate(props, cert)
    policy.sign(signature, key, cert)

    return etree.tostring(root, encoding="UTF-8", xml_declaration=True)
