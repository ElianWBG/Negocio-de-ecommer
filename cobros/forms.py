from decimal import Decimal
from django import forms
from .models import CobroFactura


class CobroFacturaForm(forms.ModelForm):
    """Formulario para registrar/editar un cobro. El campo `factura` viaja
    oculto en el formulario: se fija desde la URL (siempre se registra un
    pago PARA una factura específica, el usuario no la elige aquí)."""

    class Meta:
        model = CobroFactura
        fields = ['factura', 'fecha', 'valor', 'observacion']
        widgets = {
            'factura': forms.HiddenInput(),
            'fecha': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'valor': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'observacion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def clean(self):
        cleaned_data = super().clean()
        factura = cleaned_data.get('factura')
        valor = cleaned_data.get('valor')

        if factura is None or valor is None:
            # Ya hay errores individuales de campo; no seguimos validando cruzado.
            return cleaned_data

        if factura.estado == 'anulada':
            raise forms.ValidationError('No se puede registrar un pago sobre una factura anulada.')

        if valor <= 0:
            raise forms.ValidationError('El valor del pago debe ser mayor a cero.')

        # Saldo disponible: si estamos EDITANDO un cobro ya existente, hay que
        # "devolver" su valor anterior al saldo antes de comparar, porque ese
        # valor ya había sido restado cuando se creó por primera vez.
        saldo_disponible = factura.saldo
        if self.instance.pk:
            saldo_disponible += self.instance.valor

        if valor > saldo_disponible:
            raise forms.ValidationError(
                f'El pago (${valor}) no puede ser mayor al saldo disponible (${saldo_disponible}).'
            )

        return cleaned_data
