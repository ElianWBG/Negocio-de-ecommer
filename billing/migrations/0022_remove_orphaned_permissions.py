from django.db import migrations


def remove_orphaned_permissions(apps, schema_editor):
    """Elimina permisos cuyo ContentType apunta a un modelo que ya no existe."""
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Permission = apps.get_model('auth', 'Permission')

    orphaned_ct_ids = []
    for ct in ContentType.objects.all():
        # model_class() devuelve None cuando el modelo fue eliminado/renombrado
        try:
            from django.apps import apps as django_apps
            django_apps.get_model(ct.app_label, ct.model)
        except LookupError:
            orphaned_ct_ids.append(ct.pk)

    if orphaned_ct_ids:
        deleted, _ = Permission.objects.filter(content_type_id__in=orphaned_ct_ids).delete()
        ContentType.objects.filter(pk__in=orphaned_ct_ids).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0021_alter_auditlog_action_promotion_sent'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.RunPython(remove_orphaned_permissions, migrations.RunPython.noop),
    ]
