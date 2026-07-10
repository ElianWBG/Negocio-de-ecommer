from django.db import migrations, models


# Repinta la configuración existente a la paleta navy/azul del rediseño,
# pero SOLO en los campos que aún tienen el valor por defecto antiguo (cálido).
# Así, si el admin ya personalizó un color, se respeta.
OLD_TO_NEW = {
    'color_primario': ('#B5441B', '#2563EB'),
    'color_oscuro':   ('#231A10', '#0F1B33'),
    'color_fondo':    ('#F8F3EE', '#F3F6FC'),
    'color_navbar':   ('#231A10', '#0F1B33'),
    'color_texto':    ('#231A10', '#0F1B33'),
}


def apply_navy(apps, schema_editor):
    Config = apps.get_model('billing', 'ConfigNegocio')
    for cfg in Config.objects.all():
        changed = False
        for field, (old, new) in OLD_TO_NEW.items():
            if getattr(cfg, field, None) == old:
                setattr(cfg, field, new)
                changed = True
        if changed:
            cfg.save(update_fields=list(OLD_TO_NEW.keys()))


def revert_navy(apps, schema_editor):
    Config = apps.get_model('billing', 'ConfigNegocio')
    for cfg in Config.objects.all():
        changed = False
        for field, (old, new) in OLD_TO_NEW.items():
            if getattr(cfg, field, None) == new:
                setattr(cfg, field, old)
                changed = True
        if changed:
            cfg.save(update_fields=list(OLD_TO_NEW.keys()))


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0009_confignegocio_color_texto'),
    ]

    operations = [
        migrations.AlterField(
            model_name='confignegocio',
            name='color_primario',
            field=models.CharField(default='#2563EB', help_text='Ej: #2563EB', max_length=7, verbose_name='Color principal (hex)'),
        ),
        migrations.AlterField(
            model_name='confignegocio',
            name='color_oscuro',
            field=models.CharField(default='#0F1B33', help_text='Ej: #0F1B33', max_length=7, verbose_name='Color oscuro (hex)'),
        ),
        migrations.AlterField(
            model_name='confignegocio',
            name='color_fondo',
            field=models.CharField(default='#F3F6FC', help_text='Fondo general de la tienda', max_length=7, verbose_name='Color de fondo (hex)'),
        ),
        migrations.AlterField(
            model_name='confignegocio',
            name='color_navbar',
            field=models.CharField(default='#0F1B33', help_text='Barra de navegación superior', max_length=7, verbose_name='Color del navbar (hex)'),
        ),
        migrations.AlterField(
            model_name='confignegocio',
            name='color_texto',
            field=models.CharField(default='#0F1B33', help_text='Color principal del texto en la tienda', max_length=7, verbose_name='Color del texto (hex)'),
        ),
        migrations.RunPython(apply_navy, revert_navy),
    ]
