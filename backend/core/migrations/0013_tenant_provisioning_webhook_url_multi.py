from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_tenant_provisioning_webhook_url'),
        ('core', '0012_add_is_occupied_parked_call_uuid'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tenant',
            name='provisioning_webhook_url',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Optional URL(s) to POST the generated API key to when this tenant is created. Separate multiple URLs with commas.',
            ),
        ),
    ]
