from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('outbound_routes', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='outboundroute',
            name='caller_id_number',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Verified caller ID number to present to the carrier (e.g. 12818545006). Overrides the channel caller ID.',
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name='outboundroute',
            name='caller_id_name',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Caller ID name to present to the carrier. Defaults to caller_id_number if blank.',
                max_length=32,
            ),
        ),
    ]
