from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_user_tenant_access'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenant',
            name='voicemail_timeout',
            field=models.IntegerField(default=120, help_text='Maximum voicemail recording length in seconds.'),
        ),
    ]
