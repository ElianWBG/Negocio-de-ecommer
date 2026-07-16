from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Group, Permission
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.text import slugify
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

# Nombre del grupo con el que AdminOnlyMixin autoriza el acceso a /security/.
# Si un Administrador (no superusuario) pudiera renombrarlo o borrarlo, se
# bloquearía a sí mismo (y a todo el resto de administradores) fuera del
# panel de seguridad hasta que un superusuario lo recreara a mano.
PROTECTED_GROUP_NAME = 'Administrador'

from shared.mixins import GroupRequiredMixin, SuperuserRequiredMixin
from .forms import GroupForm, PermissionForm
from .role_presets import ROLES
from .permission_labels import (
    ACTION_COLUMNS,
    SECTION_SORT_ORDER,
    SYSTEM_SECTIONS,
    model_label_es,
    model_section_label,
    permission_action,
    permission_label_es,
)

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
    """Arma `permission_groups`: los permisos traducidos al español, agrupados
    por sección y, dentro de cada sección, por modelo — una fila por modelo con
    una columna por acción (Ver/Crear/Editar/Eliminar/Exportar). Así el
    formulario muestra ~40 filas en vez de 150 checkboxes sueltos.

    Los permisos custom que no encajan en la matriz (ej.
    descargar_reportes_financieros) caen en `extras` de su sección."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_ids = set()
        if self.object is not None:
            current_ids = set(self.object.permissions.values_list('id', flat=True))

        all_perms = list(Permission.objects.select_related('content_type').order_by(
            'content_type__app_label', 'content_type__model', 'codename'
        ))

        # sección -> {rows: {content_type_id: fila}, extras: [...]}
        sections: dict[str, dict] = {}
        for perm in all_perms:
            section_name = model_section_label(perm.content_type.app_label, perm.content_type.model)
            section = sections.setdefault(section_name, {'rows': {}, 'extras': []})
            cell = {
                'permission': perm,
                'label': permission_label_es(perm),
                'checked': perm.id in current_ids,
            }
            action = permission_action(perm)
            if action is None:
                section['extras'].append(cell)
                continue
            row = section['rows'].setdefault(perm.content_type_id, {
                'model_label': model_label_es(perm),
                'cells': {},
            })
            row['cells'][action] = cell

        def _sort_key(name):
            try:
                return SECTION_SORT_ORDER.index(name)
            except ValueError:
                return len(SECTION_SORT_ORDER)

        permission_groups = []
        for name in sorted(sections, key=_sort_key):
            section = sections[name]
            rows = []
            for row in sorted(section['rows'].values(), key=lambda r: r['model_label'].lower()):
                # Aplanar a una lista alineada con ACTION_COLUMNS: la plantilla
                # no sabe indexar un dict, y las celdas vacías deben ocupar hueco.
                rows.append({
                    'model_label': row['model_label'],
                    'cells': [row['cells'].get(action) for action, _ in ACTION_COLUMNS],
                })
            cells = [c for r in rows for c in r['cells'] if c] + section['extras']
            permission_groups.append({
                'section': name,
                'slug': slugify(name),
                'rows': rows,
                'extras': section['extras'],
                'total': len(cells),
                'checked_count': sum(1 for c in cells if c['checked']),
                'is_system': name in SYSTEM_SECTIONS,
            })

        context['permission_groups'] = permission_groups
        context['action_columns'] = [label for _, label in ACTION_COLUMNS]
        context['permission_total'] = len(all_perms)
        context['presets'] = self._build_presets(all_perms)
        return context

    def _build_presets(self, all_perms):
        """Plantillas de arranque para el formulario: los roles reales del
        sistema (los mismos que crea `setup_roles`) más atajos genéricos."""
        by_codename: dict[str, list] = {}
        for perm in all_perms:
            by_codename.setdefault(perm.codename, []).append(perm.id)

        presets = [
            {'name': 'Todo', 'ids': [p.id for p in all_perms]},
            {'name': 'Solo lectura', 'ids': [p.id for p in all_perms if p.codename.startswith('view_')]},
            {'name': 'Ninguno', 'ids': []},
        ]
        for role_name, codenames in ROLES.items():
            if codenames == '__all__':
                continue  # ya cubierto por "Todo"
            ids = [pk for cn in codenames for pk in by_codename.get(cn, [])]
            presets.append({'name': role_name, 'ids': ids})
        return presets

class _StripAuthPermissionsMixin:
    """GroupCreateView/UpdateView solo exigen ser miembro del grupo
    Administrador (AdminOnlyMixin), no ser superusuario. Pero el catálogo de
    permisos incluye los de `auth` (add_user/change_user/delete_user,
    add_group, add_permission, etc.) — de asignarse a un rol, cualquier
    usuario de ese rol con acceso a /admin/ podría gestionar usuarios y
    escalar privilegios. Un Administrador no-superusuario nunca puede dejar
    permisos de `auth` en el grupo que guarda, sin importar qué haya
    enviado el formulario."""

    def form_valid(self, form):
        response = super().form_valid(form)
        if not self.request.user.is_superuser:
            auth_perms = self.object.permissions.filter(content_type__app_label='auth')
            if auth_perms.exists():
                self.object.permissions.remove(*auth_perms)
        return response

class GroupCreateView(AdminOnlyMixin, PermissionGroupsContextMixin, _StripAuthPermissionsMixin, CreateView):
    model = Group
    form_class = GroupForm
    template_name = 'security/group_form.html'
    success_url = reverse_lazy('security:group_list')

class GroupUpdateView(AdminOnlyMixin, PermissionGroupsContextMixin, _StripAuthPermissionsMixin, UpdateView):
    model = Group
    form_class = GroupForm
    template_name = 'security/group_form.html'
    success_url = reverse_lazy('security:group_list')

    def form_valid(self, form):
        if self.object.name == PROTECTED_GROUP_NAME and form.cleaned_data['name'] != PROTECTED_GROUP_NAME:
            form.add_error('name', f'No se puede renombrar el grupo "{PROTECTED_GROUP_NAME}": es el rol que da acceso a este panel.')
            return self.form_invalid(form)
        return super().form_valid(form)

class GroupDeleteView(AdminOnlyMixin, DeleteView):
    model = Group
    template_name = 'security/confirm_delete.html'
    success_url = reverse_lazy('security:group_list')

    def form_valid(self, form):
        if self.object.name == PROTECTED_GROUP_NAME:
            messages.error(self.request, f'No se puede eliminar el grupo "{PROTECTED_GROUP_NAME}": es el rol que da acceso a este panel.')
            return redirect('security:group_list')
        return super().form_valid(form)

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
