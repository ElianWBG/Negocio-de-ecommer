from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('storefront', '0004_alter_purchaserequest_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='purchaserequest',
            name='paypal_order_id',
            field=models.CharField(blank=True, max_length=32, null=True, verbose_name='ID de orden (PayPal)'),
        ),
    ]
