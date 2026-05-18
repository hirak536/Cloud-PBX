from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fax', '0002_add_tenant'),
    ]

    operations = [
        migrations.AddField(
            model_name='faxfile',
            name='channel_uuid',
            field=models.CharField(blank=True, db_index=True, default='', max_length=64),
            preserve_default=False,
        ),
    ]
