from itertools import groupby

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Group, Permission
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from shared.mixins import GroupRequiredMixin, SuperuserRequiredMixin
from .forms import GroupForm, PermissionForm
from .permission_labels import app_section_label, permission_label_es

# === MIXIN BASE: SOLO ADMINISTRADOR ===
class AdminOnlyMixin(LoginRequiredMixin, GroupRequiredMixin):
    """Combina login + rol Administrador (el superusuario siempre pasa)."""
    group_required = ['Administrador']
    group_redirect_url = '/'

# === ROLES / GROUP (Administrador) ===
class GroupListView(AdminOnlyMixin, ListView):
    model = Group
    template_name = 'security/group_list.html'
    context_object_name = 'items'

class PermissionGroupsContextMixin:
    """Arma `permission_groups`: los permisos agrupados por app y traducidos
    al español, para que group_form.html no muestre 100+ checkboxes técnicos
    en una lista plana."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_ids = set()
        if self.object is not None:
            current_ids = set(self.object.permissions.values_list('id', flat=True))

        qs = Permission.objects.select_related('content_type').order_by(
            'content_type__app_label', 'content_type__model', 'codename'
        )
        permission_groups = []
        for app_label, perms in groupby(qs, key=lambda p: p.content_type.app_label):
            permission_groups.append({
                'section': app_section_label(app_label),
                'items': [
                    {'permission': p, 'label': permission_label_es(p), 'checked': p.id in current_ids}
                    for p in perms
                ],
            })
        permission_groups.sort(key=lambda g: g['section'])
        context['permission_groups'] = permission_groups
        return context

class GroupCreateView(AdminOnlyMixin, PermissionGroupsContextMixin, CreateView):
    model = Group
    form_class = GroupForm
    template_name = 'security/group_form.html'
    success_url = reverse_lazy('security:group_list')

class GroupUpdateView(AdminOnlyMixin, PermissionGroupsContextMixin, UpdateView):
    model = Group
    form_class = GroupForm
    template_name = 'security/group_form.html'
    success_url = reverse_lazy('security:group_list')

class GroupDeleteView(AdminOnlyMixin, DeleteView):
    model = Group
    template_name = 'security/confirm_delete.html'
    success_url = reverse_lazy('security:group_list')

# === PERMISOS / PERMISSION (lectura: Administrador · escritura: solo superusuario) ===
class PermissionListView(AdminOnlyMixin, ListView):
    model = Permission
    template_name = 'security/permission_list.html'
    context_object_name = 'items'
    queryset = Permission.objects.select_related('content_type')

class PermissionCreateView(LoginRequiredMixin, SuperuserRequiredMixin, CreateView):
    model = Permission
    form_class = PermissionForm
    template_name = 'security/permission_form.html'
    success_url = reverse_lazy('security:permission_list')

class PermissionUpdateView(LoginRequiredMixin, SuperuserRequiredMixin, UpdateView):
    model = Permission
    form_class = PermissionForm
    template_name = 'security/permission_form.html'
    success_url = reverse_lazy('security:permission_list')

class PermissionDeleteView(LoginRequiredMixin, SuperuserRequiredMixin, DeleteView):
    model = Permission
    template_name = 'security/confirm_delete.html'
    success_url = reverse_lazy('security:permission_list')
