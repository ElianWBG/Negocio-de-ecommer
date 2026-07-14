from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from billing.models import Customer, Review


class CustomerRegistrationForm(forms.Form):
    """Registro de cliente nuevo desde el catálogo público."""
    dni = forms.CharField(label='Cédula / RUC', max_length=13, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '1710034065'}))
    first_name = forms.CharField(label='Nombre', max_length=100, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(label='Apellido', max_length=100, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(label='Correo electrónico', widget=forms.EmailInput(attrs={'class': 'form-control'}))
    phone = forms.CharField(label='Teléfono', max_length=20, required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '0999999999'}))
    address = forms.CharField(label='Dirección', required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}))
    accepts_promotions = forms.BooleanField(
        label='Quiero recibir promociones y ofertas por correo',
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    password1 = forms.CharField(label='Contraseña', widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    password2 = forms.CharField(label='Confirmar contraseña', widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Ya existe una cuenta con este correo. Inicia sesión.')
        return email

    def clean_dni(self):
        from shared.validators import validate_cedula_ec
        from django.core.exceptions import ValidationError as DjangoValidationError
        dni = self.cleaned_data['dni']
        try:
            validate_cedula_ec(dni)
        except DjangoValidationError as e:
            raise forms.ValidationError(e.message)
        if Customer.objects.filter(dni=dni, user__isnull=False).exists():
            raise forms.ValidationError('Ya existe una cuenta con esta cédula. Inicia sesión.')
        return dni

    def clean_password1(self):
        password = self.cleaned_data.get('password1')
        if password:
            validate_password(password)
        return password

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password1')
        p2 = cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', 'Las contraseñas no coinciden.')
        return cleaned_data


class CustomerLoginForm(forms.Form):
    """Login de cliente desde el catálogo público."""
    email = forms.EmailField(label='Correo electrónico', widget=forms.EmailInput(attrs={'class': 'form-control'}))
    password = forms.CharField(label='Contraseña', widget=forms.PasswordInput(attrs={'class': 'form-control'}))


class CustomerRequestForm(forms.ModelForm):
    """Datos de envío/contacto al confirmar la solicitud de compra.
    Pre-rellena con los datos del cliente autenticado."""
    # El DNI NO se incluye: es inmutable tras el registro. Dejarlo en el form
    # (aunque sea readonly en HTML) permitiría cambiarlo con cualquier cliente
    # HTTP (mass assignment). El cliente ve su DNI como texto en el template.
    class Meta:
        model = Customer
        fields = ['first_name', 'last_name', 'email', 'phone', 'address']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def validate_unique(self):
        pass


REVIEW_IMAGE_ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
REVIEW_IMAGE_MAX_SIZE = 5 * 1024 * 1024
REVIEW_IMAGE_MAX_COUNT = 5


class ReviewForm(forms.ModelForm):
    """Reseña de un producto ya comprado. Una por (cliente, producto),
    reutilizable para crear o editar (se pasa instance=review existente).
    La calificación se elige con estrellas clicables en el template; este
    campo queda como input oculto que esa UI actualiza vía JS."""
    class Meta:
        model = Review
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.HiddenInput(),
            'comment': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 4,
                'placeholder': 'Cuéntanos qué te pareció el producto...',
            }),
        }
        labels = {'rating': 'Calificación', 'comment': 'Comentario'}

    def clean_comment(self):
        comment = self.cleaned_data['comment'].strip()
        if len(comment) < 5:
            raise forms.ValidationError('El comentario es demasiado corto.')
        return comment


def clean_review_images(files):
    """Valida la lista de imágenes subidas para una reseña (tamaño, tipo y
    cantidad). Se usa en la vista porque las imágenes viven en un modelo
    aparte (ReviewImage), no como campo del ReviewForm."""
    if len(files) > REVIEW_IMAGE_MAX_COUNT:
        raise forms.ValidationError(f'Puedes subir un máximo de {REVIEW_IMAGE_MAX_COUNT} imágenes.')
    for f in files:
        if f.size > REVIEW_IMAGE_MAX_SIZE:
            raise forms.ValidationError(f'"{f.name}" supera el máximo de 5MB.')
        if hasattr(f, 'content_type') and f.content_type not in REVIEW_IMAGE_ALLOWED_TYPES:
            raise forms.ValidationError(f'"{f.name}" no es un formato permitido. Use JPG, PNG, GIF o WebP.')
    return files
