def user_panel_roles(request):
    if not request.user.is_authenticated:
        return {}
    u = request.user
    # "Sistema" (config/usuarios/actividad/roles) se queda atado al grupo
    # fijo 'Administrador', no a un permiso delegable: así un rol nuevo
    # creado desde el panel nunca puede auto-otorgarse esa sección solo
    # por tener, por ejemplo, permiso de editar usuarios.
    is_admin = u.is_superuser or u.groups.filter(name='Administrador').exists()

    def any_perm(*perms):
        return is_admin or any(u.has_perm(p) for p in perms)

    return {
        'panel_is_admin': is_admin,
        # Ancladas a un permiso de ESCRITURA propio de cada rol dueño de la
        # sección (no de solo-lectura): así un rol como "Contador", que
        # necesita ver facturas/productos como contexto mas no venderlos,
        # no termina destapando toda la sección de Ventas o Catálogo.
        'panel_is_vendedor': any_perm('billing.add_invoice', 'billing.change_customer'),
        'panel_is_analista': any_perm('billing.add_product', 'purchasing.add_purchase'),
        'panel_is_finanzas': any_perm('cobros.view_cobrofactura', 'pagos.view_pagocompra'),
        'panel_is_soporte': any_perm('storefront.view_purchaserequest'),
        # Reportes: visible a cualquier rol con acceso a al menos un reporte
        'panel_can_reportes': any_perm(
            'billing.view_invoice',
            'purchasing.view_purchase',
            'billing.view_invoicedetail',
            'billing.view_product',
        ),
    }
