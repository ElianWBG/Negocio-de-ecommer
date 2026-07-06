from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0008_auditlog'),
    ]

    operations = [
        migrations.AddField(
            model_name='confignegocio',
            name='color_texto',
            field=models.CharField(
                default='#231A10',
                help_text='Color principal del texto en la tienda',
                max_length=7,
                verbose_name='Color del texto (hex)',
            ),
        ),
    ]
