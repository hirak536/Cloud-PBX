import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('extensions', '0005_add_codecs_and_forward_destinations'),
        ('gateways', '0002_add_tenant'),
    ]

    operations = [
        migrations.AddField(
            model_name='extension',
            name='outbound_route',
            field=models.ForeignKey(
                blank=True,
                null=True,
                db_column='gateway_uuid',
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='extensions',
                to='gateways.gateway',
                verbose_name='Default outbound route',
                help_text='Default SIP trunk/gateway for outbound calls from this extension.',
            ),
        ),
        migrations.AddField(
            model_name='extension',
            name='outbound_xheader_name',
            field=models.CharField(
                blank=True,
                default='',
                max_length=64,
                verbose_name='Custom X-header name',
                help_text='SIP X-header name sent on outbound calls, e.g. X-Tenant-ID.',
            ),
        ),
        migrations.AddField(
            model_name='extension',
            name='outbound_xheader_value',
            field=models.CharField(
                blank=True,
                default='',
                max_length=256,
                verbose_name='Custom X-header value',
                help_text='Value for the custom SIP X-header above.',
            ),
        ),
    ]
