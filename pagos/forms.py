from django import forms
from .models import PagoCompra


class PagoCompraForm(forms.ModelForm):
    class Meta:
        model = PagoCompra
        fields = ['compra', 'fecha', 'valor', 'observacion']
        widgets = {
            'compra': forms.HiddenInput(),
            'fecha': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'valor': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'observacion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def clean(self):
        cleaned_data = super().clean()
        compra = cleaned_data.get('compra')
        valor = cleaned_data.get('valor')

        if compra is None or valor is None:
            return cleaned_data

        if compra.estado == 'anulada':
            raise forms.ValidationError('No se puede registrar un pago sobre una compra anulada.')

        if valor <= 0:
            raise forms.ValidationError('El valor del pago debe ser mayor a cero.')

        saldo_disponible = compra.saldo
        if self.instance.pk:
            saldo_disponible += self.instance.valor

        if valor > saldo_disponible:
            raise forms.ValidationError(
                f'El pago (${valor}) no puede ser mayor al saldo disponible (${saldo_disponible}).'
            )

        return cleaned_data
