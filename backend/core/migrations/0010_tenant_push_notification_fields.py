from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_audit_log'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenant',
            name='push_notifications_enabled',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='tenant',
            name='offline_poll_timeout',
            field=models.PositiveSmallIntegerField(default=30, help_text='Seconds to wait for an offline extension to register before forwarding (1–120).'),
        ),
    ]
