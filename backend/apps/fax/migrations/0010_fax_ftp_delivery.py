from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fax', '0009_backfill_blank_station_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='fax',
            name='fax_delivery_mode',
            field=models.CharField(
                choices=[('email', 'Email'), ('ftp', 'FTP'), ('both', 'Email + FTP')],
                default='email', max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='fax',
            name='fax_ftp_host',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='fax',
            name='fax_ftp_port',
            field=models.IntegerField(default=21),
        ),
        migrations.AddField(
            model_name='fax',
            name='fax_ftp_username',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='fax',
            name='fax_ftp_password',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='fax',
            name='fax_ftp_path',
            field=models.CharField(blank=True, max_length=512),
        ),
        migrations.AddField(
            model_name='fax',
            name='fax_ftp_use_tls',
            field=models.BooleanField(default=False),
        ),
    ]
