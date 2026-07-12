from django import forms
from django.utils import timezone

from .models import PagoCuotaVenta


class GenerarCuotasForm(forms.Form):
    numero_cuotas = forms.IntegerField(
        min_value=1,
        label='Número de cuotas',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
    )


class PagoCuotaVentaForm(forms.ModelForm):
    class Meta:
        model = PagoCuotaVenta
        fields = ['cuota', 'fecha', 'valor', 'observacion']
        widgets = {
            'cuota': forms.HiddenInput(),
            'fecha': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'valor': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'observacion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def clean(self):
        cleaned_data = super().clean()
        cuota = cleaned_data.get('cuota')
        valor = cleaned_data.get('valor')
        fecha = cleaned_data.get('fecha')

        if cuota is None or valor is None or fecha is None:
            return cleaned_data

        if cuota.estado == 'pagada':
            raise forms.ValidationError('Esta cuota ya está pagada.')

        if valor <= 0:
            raise forms.ValidationError('El valor del pago debe ser mayor a cero.')

        if valor > cuota.saldo:
            raise forms.ValidationError(
                f'El pago (${valor}) no puede ser mayor al saldo de la cuota (${cuota.saldo}).'
            )

        fecha_factura = cuota.factura.invoice_date.date()
        if fecha > timezone.localdate():
            raise forms.ValidationError('La fecha de pago no puede ser posterior a hoy.')
        if fecha < fecha_factura:
            raise forms.ValidationError('La fecha de pago no puede ser anterior a la fecha de la factura.')

        return cleaned_data
