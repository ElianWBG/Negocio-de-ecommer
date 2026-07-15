from django.contrib.auth.models import Group, Permission, User
from django.test import TestCase
from django.urls import reverse

from .permission_labels import SYSTEM_SECTIONS


class GroupFormPermissionMatrixTests(TestCase):
    """El formulario de roles agrupa 120+ permisos en una matriz modelo × acción.
    Lo que se protege aquí es que ningún permiso se pierda por el camino: un
    permiso sin checkbox es un permiso imposible de asignar desde el panel."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('admin_test', 'a@t.com', 'x')
        cls.group = Group.objects.create(name='Rol de prueba')
        cls.group.permissions.set(Permission.objects.filter(codename='view_invoice'))

    def setUp(self):
        self.client.force_login(self.admin)

    def _groups(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return response, response.context['permission_groups']

    def test_every_permission_has_a_checkbox(self):
        _, groups = self._groups(reverse('security:group_create'))
        rendered = set()
        for group in groups:
            for row in group['rows']:
                rendered.update(cell['permission'].id for cell in row['cells'] if cell)
            rendered.update(cell['permission'].id for cell in group['extras'])

        self.assertEqual(rendered, set(Permission.objects.values_list('id', flat=True)))

    def test_custom_permissions_land_in_extras(self):
        """descargar_reportes_financieros no encaja en la matriz (no es
        view/add/change/delete) y debe caer en los extras de su sección."""
        _, groups = self._groups(reverse('security:group_create'))
        extras = {
            cell['permission'].codename
            for group in groups for cell in group['extras']
        }
        self.assertIn('descargar_reportes_financieros', extras)

    def test_export_permissions_use_the_export_column(self):
        _, groups = self._groups(reverse('security:group_create'))
        catalog = next(g for g in groups if g['section'] == 'Catálogo — Productos')
        product = next(r for r in catalog['rows'] if r['model_label'].lower() == 'producto')
        # ACTION_COLUMNS: Ver, Crear, Editar, Eliminar, Exportar
        self.assertEqual(len(product['cells']), 5)
        self.assertEqual(product['cells'][0]['permission'].codename, 'view_product')
        self.assertEqual(product['cells'][4]['permission'].codename, 'export_product')

    def test_rows_without_an_action_leave_an_empty_cell(self):
        """La mayoría de modelos no tiene permiso de exportar: su celda va vacía,
        no desplazada — si no, las columnas se desalinean."""
        _, groups = self._groups(reverse('security:group_create'))
        for group in groups:
            for row in group['rows']:
                self.assertEqual(len(row['cells']), 5, row['model_label'])

    def test_counts_reflect_the_edited_role(self):
        _, groups = self._groups(reverse('security:group_update', args=[self.group.pk]))
        invoices = next(g for g in groups if g['section'] == 'Facturas y ventas')
        self.assertEqual(invoices['checked_count'], 1)
        self.assertTrue(invoices['total'] > 1)
        # El resto de secciones no hereda marcas del rol editado.
        self.assertEqual(sum(g['checked_count'] for g in groups), 1)

    def test_system_sections_are_flagged(self):
        _, groups = self._groups(reverse('security:group_create'))
        flagged = {g['section'] for g in groups if g['is_system']}
        self.assertEqual(flagged, SYSTEM_SECTIONS & {g['section'] for g in groups})
        self.assertIn('Sesiones (sistema)', flagged)
        # Las secciones de negocio nunca se pliegan como "avanzado".
        self.assertNotIn('Facturas y ventas', flagged)

    def test_presets_map_to_real_permission_ids(self):
        response, _ = self._groups(reverse('security:group_create'))
        presets = {p['name']: p['ids'] for p in response.context['presets']}

        self.assertEqual(presets['Ninguno'], [])
        self.assertEqual(len(presets['Todo']), Permission.objects.count())
        self.assertEqual(
            set(presets['Solo lectura']),
            set(Permission.objects.filter(codename__startswith='view_').values_list('id', flat=True)),
        )
        # Los roles reales del sistema se ofrecen como plantilla, salvo
        # Administrador (que es "Todo").
        self.assertIn('Vendedor', presets)
        self.assertNotIn('Administrador', presets)
        vendedor = set(Permission.objects.filter(id__in=presets['Vendedor']).values_list('codename', flat=True))
        self.assertIn('view_invoice', vendedor)
        self.assertNotIn('delete_supplier', vendedor)

    def test_saving_the_form_persists_the_checked_permissions(self):
        perms = list(Permission.objects.filter(
            codename__in=['view_product', 'add_product', 'export_product']
        ))
        response = self.client.post(reverse('security:group_update', args=[self.group.pk]), {
            'name': 'Rol de prueba',
            'permissions': [p.id for p in perms],
        })
        self.assertEqual(response.status_code, 302)
        self.group.refresh_from_db()
        self.assertEqual(
            set(self.group.permissions.values_list('codename', flat=True)),
            {'view_product', 'add_product', 'export_product'},
        )
