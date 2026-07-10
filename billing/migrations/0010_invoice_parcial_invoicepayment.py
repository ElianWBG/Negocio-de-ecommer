import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0009_confignegocio_color_texto'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Expand Invoice.estado choices to include 'parcial'
        migrations.AlterField(
            model_name='invoice',
            name='estado',
            field=models.CharField(
                choices=[
                    ('pendiente', 'Pendiente'),
                    ('parcial', 'Parcial'),
                    ('pagada', 'Pagada'),
                    ('anulada', 'Anulada'),
                ],
                default='pendiente',
                max_length=10,
                verbose_name='Estado de pago',
            ),
        ),
        # Create InvoicePayment model
        migrations.CreateModel(
            name='InvoicePayment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12, verbose_name='Monto pagado')),
                ('payment_date', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de pago')),
                ('method', models.CharField(
                    choices=[
                        ('efectivo', 'Efectivo'),
                        ('transferencia', 'Transferencia'),
                        ('tarjeta', 'Tarjeta'),
                        ('otro', 'Otro'),
                    ],
                    max_length=15,
                    verbose_name='Método de pago',
                )),
                ('notes', models.TextField(blank=True, verbose_name='Notas')),
                ('invoice', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='payments',
                    to='billing.invoice',
                    verbose_name='Factura',
                )),
                ('registered_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Registrado por',
                )),
            ],
            options={
                'verbose_name': 'Pago de factura',
                'verbose_name_plural': 'Pagos de facturas',
                'ordering': ['-payment_date'],
            },
        ),
    ]
