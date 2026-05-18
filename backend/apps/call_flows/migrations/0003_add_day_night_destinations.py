import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('call_flows', '0002_add_tenant'),
    ]

    operations = [
        migrations.AddField(
            model_name='callflow',
            name='day_dest_type',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name='callflow',
            name='day_dest_target_uuid',
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='callflow',
            name='day_dest_external_number',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name='callflow',
            name='night_dest_type',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name='callflow',
            name='night_dest_target_uuid',
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='callflow',
            name='night_dest_external_number',
            field=models.CharField(blank=True, max_length=64),
        ),
    ]
