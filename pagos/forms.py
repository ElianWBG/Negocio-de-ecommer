from django import forms
from .models import PagoCompra


class PagoCompraForm(forms.ModelForm):
    """La compra NUNCA se toma del formulario/POST: siempre se fija en el
    constructor a partir de la URL (creación) o de la instancia existente
    (edición), para que un POST manipulado no pueda aplicar el pago contra
    una compra distinta.

    La validación de saldo hecha aquí es solo de UX (feedback inmediato al
    usuario); la comprobación que realmente protege contra pagos
    concurrentes se repite en la vista, dentro de la transacción, sobre la
    fila ya bloqueada con select_for_update()."""

    class Meta:
        model = PagoCompra
        fields = ['fecha', 'valor', 'observacion']
        widgets = {
            'fecha': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'valor': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'observacion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, compra=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.compra = compra or (self.instance.compra if self.instance.pk else None)

    def clean(self):
        cleaned_data = super().clean()
        compra = self.compra
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

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.compra = self.compra
        if commit:
            instance.save()
        return instance
