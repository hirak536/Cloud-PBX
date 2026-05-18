from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_tenant_voicemail_timeout'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='full_name',
            field=models.CharField(blank=True, default='', max_length=256),
        ),
        migrations.AddField(
            model_name='user',
            name='must_change_password',
            field=models.BooleanField(default=False),
        ),
    ]
