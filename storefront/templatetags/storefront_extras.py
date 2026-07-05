import re
from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key, 0)

@register.filter
def wa_digits(value):
    """Normaliza un número a formato internacional para wa.me/<numero>.
    Misma lógica que normalize_ec en storefront.views (Ecuador):
    quita símbolos y convierte 09XXXXXXXX -> 5939XXXXXXXX."""
    digits = re.sub(r'\D', '', str(value or ''))
    if not digits:
        return ''
    if digits.startswith('593'):
        return digits
    if digits.startswith('0'):        # 0991509228 -> 593991509228
        return '593' + digits[1:]
    if len(digits) == 9:              # 991509228  -> 593991509228
        return '593' + digits
    return digits
