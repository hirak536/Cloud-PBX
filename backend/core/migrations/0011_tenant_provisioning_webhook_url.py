from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_tenant_push_notification_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenant',
            name='provisioning_webhook_url',
            field=models.URLField(
                blank=True,
                default='',
                help_text='Optional URL to POST the generated API key to when this tenant is created.',
                max_length=512,
            ),
        ),
    ]
