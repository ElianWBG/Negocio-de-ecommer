from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0019_alter_brand_options_alter_confignegocio_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='confignegocio',
            name='razon_social',
            field=models.CharField(blank=True, max_length=300, verbose_name='Razón social', help_text='Nombre legal registrado en el SRI. Ej: TECNOLOGÍA AVANZADA S.A.'),
        ),
        migrations.AddField(
            model_name='confignegocio',
            name='nombre_comercial',
            field=models.CharField(blank=True, max_length=300, verbose_name='Nombre comercial', help_text='Nombre de fantasía que aparece en el RIDE. Puede coincidir con la razón social.'),
        ),
        migrations.AddField(
            model_name='confignegocio',
            name='codigo_establecimiento',
            field=models.CharField(default='001', max_length=3, verbose_name='Código establecimiento', help_text='3 dígitos. Ej: 001'),
        ),
        migrations.AddField(
            model_name='confignegocio',
            name='punto_emision',
            field=models.CharField(default='001', max_length=3, verbose_name='Punto de emisión', help_text='3 dígitos. Ej: 001'),
        ),
        migrations.AddField(
            model_name='confignegocio',
            name='ambiente_sri',
            field=models.CharField(
                choices=[('1', 'Pruebas'), ('2', 'Producción')],
                default='1',
                max_length=1,
                verbose_name='Ambiente SRI',
            ),
        ),
        migrations.AddField(
            model_name='confignegocio',
            name='obligado_contabilidad',
            field=models.BooleanField(default=False, verbose_name='Obligado a llevar contabilidad'),
        ),
        migrations.AddField(
            model_name='confignegocio',
            name='contribuyente_especial',
            field=models.CharField(blank=True, max_length=10, verbose_name='Número contribuyente especial', help_text='Dejar vacío si no aplica'),
        ),
    ]
