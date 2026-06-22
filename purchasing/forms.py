from django import forms
from django.forms import inlineformset_factory
from .models import Purchase, PurchaseDetail


class PurchaseForm(forms.ModelForm):
    """Formulario para la cabecera de la compra."""
    class Meta:
        model = Purchase
        fields = ['supplier', 'document_number']
        widgets = {
            'supplier': forms.Select(attrs={'class': 'form-select'}),
            'document_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'N° de factura del proveedor',
            }),
        }


# Formset: permite agregar MÚLTIPLES líneas de producto dentro de UNA compra.
# extra=3: muestra 3 filas vacías para agregar productos.
# can_delete=True: permite eliminar filas.
PurchaseDetailFormSet = inlineformset_factory(
    Purchase,           # Modelo padre
    PurchaseDetail,     # Modelo hijo
    fields=['product', 'quantity', 'unit_cost'],
    extra=3,
    can_delete=True,
    widgets={
        'product': forms.Select(attrs={'class': 'form-select'}),
        'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        'unit_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0}),
    }
)
