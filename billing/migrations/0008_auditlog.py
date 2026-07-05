from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0007_brand_whatsapp_confignegocio_color_fondo_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[
                    ('created', 'Creado'),
                    ('updated', 'Actualizado'),
                    ('deleted', 'Eliminado'),
                    ('confirmed', 'Confirmado'),
                    ('rejected', 'Rechazado'),
                    ('login', 'Inicio de sesión'),
                    ('config_saved', 'Configuración guardada'),
                ], max_length=20)),
                ('model_name', models.CharField(max_length=100)),
                ('object_id', models.IntegerField(blank=True, null=True)),
                ('description', models.TextField()),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='audit_logs',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Registro de actividad',
                'verbose_name_plural': 'Registros de actividad',
                'ordering': ['-timestamp'],
            },
        ),
    ]
