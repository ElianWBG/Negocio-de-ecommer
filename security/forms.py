from django import forms
from django.contrib.auth.models import Group, Permission

# === ROLES (Group) CON SUS PERMISOS ===
class GroupForm(forms.ModelForm):
    """Crear/editar un rol y marcar sus permisos con checkboxes."""
    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.select_related('content_type').order_by(
            'content_type__app_label', 'content_type__model', 'codename'
        ),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Permisos',
    )

    class Meta:
        model = Group
        fields = ['name', 'permissions']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'name': 'Nombre del rol',
        }

# === PERMISOS PERSONALIZADOS (solo superusuario) ===
class PermissionForm(forms.ModelForm):
    """Crear un permiso propio, ej: can_approve_invoice."""
    class Meta:
        model = Permission
        fields = ['name', 'codename', 'content_type']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'codename': forms.TextInput(attrs={'class': 'form-control'}),
            'content_type': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'name': 'Nombre visible',
            'codename': 'Código interno',
            'content_type': 'Modelo al que aplica',
        }
