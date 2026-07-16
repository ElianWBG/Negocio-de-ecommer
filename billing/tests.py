from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.views import View

from shared.validators import validate_cedula_ec
from shared.mixins import StaffRequiredMixin
from shared.decorators import audit_action


class SharedValidatorsTestCase(TestCase):
    def test_valid_cedula(self):
        # 1710034065 es una cédula ecuatoriana válida
        self.assertEqual(validate_cedula_ec("1710034065"), "1710034065")

    def test_valid_ruc(self):
        # RUC válido (cédula + 001)
        self.assertEqual(validate_cedula_ec("1710034065001"), "1710034065001")

    def test_invalid_length(self):
        with self.assertRaises(ValidationError) as context:
            validate_cedula_ec("171003406")
        self.assertEqual(context.exception.code, 'invalid_length')

    def test_invalid_chars(self):
        with self.assertRaises(ValidationError) as context:
            validate_cedula_ec("171003406a")
        self.assertEqual(context.exception.code, 'invalid_chars')

    def test_invalid_province(self):
        # Provincia 99 no existe en Ecuador
        with self.assertRaises(ValidationError) as context:
            validate_cedula_ec("9910034065")
        self.assertEqual(context.exception.code, 'invalid_province')

    def test_invalid_third_digit(self):
        # Tercer dígito >= 6 no es para persona natural en cédula
        with self.assertRaises(ValidationError) as context:
            validate_cedula_ec("1770034065")
        self.assertEqual(context.exception.code, 'invalid_third')

    def test_invalid_verifier_digit(self):
        # Dígito verificador incorrecto (debería ser 5, ponemos 4)
        with self.assertRaises(ValidationError) as context:
            validate_cedula_ec("1710034064")
        self.assertEqual(context.exception.code, 'invalid_verifier')


class StaffRequiredMixinTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.regular_user = User.objects.create_user(username='regular', password='password')
        self.staff_user = User.objects.create_user(username='staff', password='password', is_staff=True)

        # Crear una clase de vista de prueba real usando el mixin. Debe heredar
        # de View y NO sobrescribir dispatch, para que se ejecute el dispatch
        # del mixin (StaffRequiredMixin.dispatch delega en super() al aprobar).
        class DummyView(StaffRequiredMixin, View):
            def get(self, request, *args, **kwargs):
                return HttpResponse("Success")

        self.view_class = DummyView

    def test_non_staff_redirect(self):
        request = self.factory.get('/')
        request.user = self.regular_user

        # FallbackStorage instancia SessionStorage, que en Django 6 exige
        # request.session. RequestFactory no la añade, así que la creamos aquí.
        from django.contrib.sessions.backends.db import SessionStore
        request.session = SessionStore()
        # Necesitamos configurar el storage de mensajes
        setattr(request, '_messages', FallbackStorage(request))
        
        view = self.view_class()
        response = view.dispatch(request)
        
        # Debe redirigir (status code 302)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')

    def test_staff_allowed(self):
        request = self.factory.get('/')
        request.user = self.staff_user
        
        view = self.view_class()
        response = view.dispatch(request)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"Success")


class AuditActionDecoratorTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username='auditor', password='password')

        @audit_action("TEST_ACTION")
        def dummy_view(request):
            return HttpResponse("Decorated Success")

        self.view_func = dummy_view

    def test_audit_action_logging(self):
        request = self.factory.get('/')
        request.user = self.user
        
        response = self.view_func(request)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"Decorated Success")
