from django import forms
from .models import Product

class ProductForm(forms.ModelForm):
    """Formulario profesional para crear/editar productos con validaciones y estilos modernos."""
    
    class Meta:
        model = Product
        fields = ['name', 'description', 'brand', 'group', 'suppliers', 'unit_price', 'stock', 'image', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Laptop HP 15.6"',
                'autocomplete': 'off',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe las características del producto...',
                'autocomplete': 'off',
            }),
            'brand': forms.Select(attrs={
                'class': 'form-select',
            }),
            'group': forms.Select(attrs={
                'class': 'form-select',
            }),
            'suppliers': forms.SelectMultiple(attrs={
                'class': 'form-select',
                'size': 5,
            }),
            'unit_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0.01',
                'autocomplete': 'off',
            }),
            'stock': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0',
                'step': '1',
                'min': '0',
                'autocomplete': 'off',
            }),
            'image': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }
        labels = {
            'name': '📦 Nombre del Producto',
            'description': '📝 Descripción',
            'brand': '🏷️ Marca',
            'group': '📂 Grupo/Categoría',
            'suppliers': '🚚 Proveedores',
            'unit_price': '💵 Precio Unitario',
            'stock': '📊 Stock',
            'image': '🖼️ Imagen del Producto',
            'is_active': 'Producto Activo',
        }
        help_texts = {
            'name': 'Nombre único del producto. Máximo 200 caracteres.',
            'description': 'Descripción detallada del producto (opcional).',
            'brand': 'Selecciona la marca del producto.',
            'group': 'Categoría o grupo del producto.',
            'suppliers': 'Proveedores disponibles (puedes seleccionar varios).',
            'unit_price': 'Precio unitario. Debe ser mayor que cero.',
            'stock': 'Cantidad disponible en inventario.',
            'image': 'Imagen representativa (JPG, PNG, GIF, WebP - máx 5MB).',
            'is_active': 'Marca para mostrar este producto en listados.',
        }
        error_messages = {
            'name': {
                'required': 'El nombre del producto es obligatorio.',
                'max_length': 'El nombre no debe superar los 200 caracteres.',
            },
            'brand': {
                'required': 'Debe seleccionar una marca para el producto.',
            },
            'group': {
                'required': 'Debe seleccionar un grupo/categoría para el producto.',
            },
            'unit_price': {
                'required': 'El precio unitario es obligatorio.',
                'invalid': 'Por favor, ingrese un precio numérico válido.',
            },
            'stock': {
                'required': 'El stock es obligatorio.',
                'invalid': 'Por favor, ingrese un número entero válido para el stock.',
            }
        }

    def clean_unit_price(self):
        """Validar que el precio unitario sea mayor que cero."""
        unit_price = self.cleaned_data.get('unit_price')
        if unit_price is not None and unit_price <= 0:
            raise forms.ValidationError('El precio unitario debe ser mayor que cero.')
        return unit_price

    def clean_stock(self):
        """Validar que el stock no sea negativo."""
        stock = self.cleaned_data.get('stock')
        if stock is not None and stock < 0:
            raise forms.ValidationError('El stock no puede ser negativo.')
        return stock

    def clean_image(self):
        """Validar tamaño y tipo de imagen."""
        image = self.cleaned_data.get('image')
        if image and hasattr(image, 'content_type'):
            # Validar tamaño (máx 5MB)
            if image.size > 5 * 1024 * 1024:
                raise forms.ValidationError('La imagen no debe superar 5MB.')
            # Validar tipo
            allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
            if image.content_type not in allowed_types:
                raise forms.ValidationError('Formato de imagen no permitido. Use JPG, PNG, GIF o WebP.')
        return image

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Aplicar clases adicionales a campos requeridos
        for field_name, field in self.fields.items():
            if field.required:
                field.widget.attrs.setdefault('required', 'required')
