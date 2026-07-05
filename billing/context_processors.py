def user_panel_roles(request):
    if not request.user.is_authenticated:
        return {}
    is_admin = request.user.is_superuser or request.user.groups.filter(name='Administrador').exists()
    is_vendedor = is_admin or request.user.groups.filter(name='Vendedor').exists()
    is_analista = is_admin or request.user.groups.filter(name='Analista de Compras').exists()
    return {
        'panel_is_admin': is_admin,
        'panel_is_vendedor': is_vendedor,
        'panel_is_analista': is_analista,
    }
