from django import forms
from django.forms import inlineformset_factory
from .models import Purchase, PurchaseDetail


class PurchaseForm(forms.ModelForm):
    """Formulario para la cabecera de la compra."""

    numero_cuotas = forms.IntegerField(
        required=False, min_value=1,
        label='Número de cuotas',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
    )

    class Meta:
        model = Purchase
        fields = ['supplier', 'document_number', 'tipo_pago']
        widgets = {
            'supplier': forms.Select(attrs={'class': 'form-select'}),
            'document_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'N° de factura del proveedor',
            }),
            'tipo_pago': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        numero_cuotas = cleaned_data.get('numero_cuotas')
        if numero_cuotas and cleaned_data.get('tipo_pago') != 'credito':
            self.add_error('numero_cuotas', 'El número de cuotas solo aplica a compras a crédito.')
        return cleaned_data


# Formset: permite agregar MÚLTIPLES líneas de producto dentro de UNA compra.
# extra=3: muestra 3 filas vacías para agregar productos.
# can_delete=True: permite eliminar filas.
PurchaseDetailFormSet = inlineformset_factory(
    Purchase,           # Modelo padre
    PurchaseDetail,     # Modelo hijo
    fields=['product', 'quantity', 'unit_cost'],
    extra=3,
    can_delete=True,
    min_num=1,
    validate_min=True,
    widgets={
        'product': forms.Select(attrs={'class': 'form-select'}),
        'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        'unit_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0}),
    }
)
