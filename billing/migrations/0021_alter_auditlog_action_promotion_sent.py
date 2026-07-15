from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0020_confignegocio_sri_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='auditlog',
            name='action',
            field=models.CharField(
                choices=[
                    ('created',        'Creado'),
                    ('updated',        'Actualizado'),
                    ('deleted',        'Eliminado'),
                    ('confirmed',      'Confirmado'),
                    ('rejected',       'Rechazado'),
                    ('login',          'Inicio de sesión'),
                    ('config_saved',   'Configuración guardada'),
                    ('promotion_sent', 'Promoción enviada'),
                ],
                max_length=20,
            ),
        ),
    ]
