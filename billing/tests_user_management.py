from django.contrib.auth.models import User, Group, Permission
from django.test import TestCase
from django.urls import reverse

from security.views import PROTECTED_GROUP_NAME


class UserManagementPrivilegeEscalationTestCase(TestCase):
    """Regresión de la guardia de escalada de privilegios en
    billing.views.user_management: un no-superusuario con auth.change_user /
    auth.add_user NO puede otorgar el rol protegido 'Administrador' ni tocar
    cuentas de superusuario. Un superusuario sí puede."""

    @classmethod
    def setUpTestData(cls):
        cls.admin_group = Group.objects.get_or_create(name=PROTECTED_GROUP_NAME)[0]
        cls.normal_group = Group.objects.get_or_create(name='Vendedor')[0]

        # Actor no-superusuario, pero con los permisos que dan acceso a la
        # pantalla de gestión de usuarios.
        cls.manager = User.objects.create_user(username='manager', password='x', is_staff=True)
        cls.manager.user_permissions.add(
            Permission.objects.get(content_type__app_label='auth', codename='change_user'),
            Permission.objects.get(content_type__app_label='auth', codename='add_user'),
        )

        cls.superuser = User.objects.create_superuser(username='root', password='x', email='root@x.com')
        cls.victim = User.objects.create_user(username='victima', password='x')

    # --- set_group ---

    def test_no_super_no_puede_asignar_grupo_administrador(self):
        self.client.force_login(self.manager)
        self.client.post(reverse('billing:user_management'), {
            'action': 'set_group', 'user_id': self.victim.pk, 'group_name': PROTECTED_GROUP_NAME,
        })
        self.assertFalse(
            self.victim.groups.filter(name=PROTECTED_GROUP_NAME).exists(),
            'Un no-superusuario logró asignar el rol Administrador (escalada).',
        )

    def test_no_super_no_puede_cambiar_rol_de_un_superusuario(self):
        self.client.force_login(self.manager)
        self.client.post(reverse('billing:user_management'), {
            'action': 'set_group', 'user_id': self.superuser.pk, 'group_name': 'Vendedor',
        })
        self.assertFalse(
            self.superuser.groups.filter(name='Vendedor').exists(),
            'Un no-superusuario logró modificar los grupos de un superusuario.',
        )

    def test_no_super_no_puede_degradar_a_un_administrador_existente(self):
        self.victim.groups.add(self.admin_group)
        self.client.force_login(self.manager)
        self.client.post(reverse('billing:user_management'), {
            'action': 'set_group', 'user_id': self.victim.pk, 'group_name': 'Vendedor',
        })
        self.assertTrue(
            self.victim.groups.filter(name=PROTECTED_GROUP_NAME).exists(),
            'Un no-superusuario logró cambiarle el rol a un Administrador existente.',
        )

    def test_no_super_si_puede_asignar_un_grupo_normal(self):
        self.client.force_login(self.manager)
        self.client.post(reverse('billing:user_management'), {
            'action': 'set_group', 'user_id': self.victim.pk, 'group_name': 'Vendedor',
        })
        self.assertTrue(
            self.victim.groups.filter(name='Vendedor').exists(),
            'La guardia bloqueó una asignación de rol legítima.',
        )

    def test_superusuario_si_puede_asignar_administrador(self):
        self.client.force_login(self.superuser)
        self.client.post(reverse('billing:user_management'), {
            'action': 'set_group', 'user_id': self.victim.pk, 'group_name': PROTECTED_GROUP_NAME,
        })
        self.assertTrue(
            self.victim.groups.filter(name=PROTECTED_GROUP_NAME).exists(),
            'La guardia impidió a un superusuario asignar Administrador.',
        )

    # --- create_user ---

    def test_no_super_no_puede_crear_usuario_administrador(self):
        self.client.force_login(self.manager)
        self.client.post(reverse('billing:user_management'), {
            'action': 'create_user', 'username': 'nuevo_admin',
            'email': 'nuevo_admin@x.com', 'group_name': PROTECTED_GROUP_NAME,
        })
        self.assertFalse(
            User.objects.filter(username='nuevo_admin').exists(),
            'Un no-superusuario creó un usuario con rol Administrador (escalada).',
        )

    def test_superusuario_si_puede_crear_usuario_administrador(self):
        self.client.force_login(self.superuser)
        self.client.post(reverse('billing:user_management'), {
            'action': 'create_user', 'username': 'nuevo_admin',
            'email': 'nuevo_admin@x.com', 'group_name': PROTECTED_GROUP_NAME,
        })
        nuevo = User.objects.filter(username='nuevo_admin').first()
        self.assertIsNotNone(nuevo, 'Un superusuario no pudo crear el usuario Administrador.')
        self.assertTrue(nuevo.groups.filter(name=PROTECTED_GROUP_NAME).exists())
