from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fax', '0006_faxfile_direction'),
    ]

    operations = [
        migrations.AddField(
            model_name='faxfile',
            name='fax_file_caller_id_name',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='faxfile',
            name='fax_file_station_id',
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
