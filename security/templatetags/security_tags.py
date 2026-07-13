from django import template

from security.permission_labels import permission_label_es, model_section_label

register = template.Library()

@register.filter(name='label_es')
def label_es(permission):
    """{{ permission|label_es }} -> 'Ver factura'"""
    return permission_label_es(permission)

@register.filter(name='section_label_es')
def section_label_es(app_label):
    """{{ app_label|section_label_es }} -> 'Clientes'"""
    return model_section_label(app_label, '')

@register.filter(name='has_group')
def has_group(user, group_name):
    """
    Uso en template:
        {% load security_tags %}
        {% if user|has_group:'Vendedor' %} ... {% endif %}
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:      # el superusuario ve todo
        return True
    return user.groups.filter(name=group_name).exists()
