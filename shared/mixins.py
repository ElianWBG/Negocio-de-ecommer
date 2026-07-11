from django.contrib import messages
from django.contrib.auth.mixins import AccessMixin
from django.shortcuts import redirect


class GroupRequiredMixin(AccessMixin):
    """
    Verifica que el usuario pertenezca a al menos uno de los grupos indicados.
    Los superusuarios pasan siempre. Si no cumple, redirige a billing:home.

    Uso:
        class ProductListView(GroupRequiredMixin, ListView):
            group_required = ['Analista de Compras', 'Administrador']
    """

    group_required = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_superuser and self.group_required:
            user_groups = set(request.user.groups.values_list('name', flat=True))
            if not user_groups.intersection(set(self.group_required)):
                messages.error(request, 'No tienes permisos para acceder a esta sección.')
                return redirect('billing:home')
        return super().dispatch(request, *args, **kwargs)


class PermissionRequiredAnyMixin(AccessMixin):
    """
    Verifica que el usuario tenga al menos uno de los permisos indicados
    (formato 'app_label.codename'). Los superusuarios pasan siempre.
    Si no cumple, redirige a billing:home.

    Uso:
        class InvoiceListView(PermissionRequiredAnyMixin, ListView):
            permissions_required = ['billing.view_invoice']
    """

    permissions_required = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_superuser and self.permissions_required:
            if not any(request.user.has_perm(p) for p in self.permissions_required):
                messages.error(request, 'No tienes permisos para acceder a esta sección.')
                return redirect('billing:home')
        return super().dispatch(request, *args, **kwargs)


class SuperuserRequiredMixin(AccessMixin):
    """
    Verifica que el usuario sea superusuario. Se usa para acciones sensibles
    que ni siquiera el rol Administrador debe poder hacer, como crear
    permisos personalizados.

    Uso:
        class PermissionCreateView(LoginRequiredMixin, SuperuserRequiredMixin, CreateView):
            ...
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_superuser:
            messages.error(request, 'Solo el superusuario puede realizar esta acción.')
            return redirect('billing:home')
        return super().dispatch(request, *args, **kwargs)


class StaffRequiredMixin:
    """
    Mixin que verifica si el usuario es miembro del staff.
    Si no es staff, redirige con mensaje de error.
    
    Uso:
        class BrandDeleteView(LoginRequiredMixin, StaffRequiredMixin, DeleteView):
            ...
    
    ¿POR QUÉ?
    Porque solo el personal autorizado (staff) debe poder
    eliminar registros. Un usuario normal puede ver y crear,
    pero no borrar información importante del sistema.
    
    ¿CÓMO FUNCIONA?
    1. El usuario intenta acceder a una vista protegida
    2. dispatch() se ejecuta ANTES que la vista
    3. Si user.is_staff es False → redirige con mensaje de error
    4. Si user.is_staff es True → ejecuta la vista normalmente
    """

    # URL a donde redirigir si no es staff
    # Se puede sobreescribir en cada vista
    staff_redirect_url = '/'
    staff_error_message = 'You do not have permission to perform this action. Staff access required.'

    def dispatch(self, request, *args, **kwargs):
        """
        dispatch() es el primer método que se ejecuta en una CBV.
        Interceptamos aquí para verificar permisos ANTES de
        procesar la petición (GET o POST).
        """
        # Verificar si el usuario es staff
        if not request.user.is_staff:
            # Mostrar mensaje de error al usuario
            messages.error(request, self.staff_error_message)
            # Redirigir a la URL configurada
            return redirect(self.staff_redirect_url)

        # Si es staff, continuar con el flujo normal de la vista
        return super().dispatch(request, *args, **kwargs)
