from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('purchasing', '0002_purchase_estado_purchase_saldo_purchase_tipo_pago'),
    ]

    operations = [
        migrations.AlterField(
            model_name='purchase',
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
    ]
