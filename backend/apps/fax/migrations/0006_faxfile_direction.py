from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fax', '0005_faxfile_retry_count'),
    ]

    operations = [
        migrations.AddField(
            model_name='faxfile',
            name='direction',
            field=models.CharField(
                choices=[('inbound', 'Inbound'), ('outbound', 'Outbound')],
                default='outbound',
                max_length=10,
            ),
        ),
    ]
