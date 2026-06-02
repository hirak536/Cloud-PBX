from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('client_api', '0003_tenantapikey_push_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tenantapikey',
            name='webhook_url',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='webhookdelivery',
            name='url',
            field=models.TextField(blank=True, default=''),
        ),
    ]
