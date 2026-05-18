import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('destinations', '0005_merge_20260223_1013'),
    ]

    operations = [
        migrations.AddField(
            model_name='destination',
            name='destination_name',
            field=models.CharField(blank=True, default='', help_text='Friendly name for this DID, e.g. "IHS Main".', max_length=128),
        ),
        migrations.AddField(
            model_name='destination',
            name='max_channels',
            field=models.IntegerField(blank=True, help_text='Maximum simultaneous inbound calls. Null = unlimited.', null=True),
        ),
        migrations.AddField(
            model_name='destination',
            name='notify_over_limit',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='destination',
            name='use_cnam_service',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='destination',
            name='hide_callerid',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='destination',
            name='use_as_emergency_callerid',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='destination',
            name='inbound_call_rate',
            field=models.CharField(blank=True, default='', help_text='Per-minute rate applied to inbound calls.', max_length=64),
        ),
        migrations.AddField(
            model_name='destination',
            name='unconditional_forward',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='destination',
            name='always_record',
            field=models.CharField(
                blank=True, default='', max_length=16,
                choices=[('', 'No'), ('all', 'All'), ('local', 'Local'), ('outbound', 'Outbound'), ('inbound', 'Inbound')],
            ),
        ),
        migrations.AddField(
            model_name='destination',
            name='email_recording_to',
            field=models.EmailField(blank=True, default='', max_length=254),
        ),
        migrations.AddField(
            model_name='destination',
            name='transcript_recorded',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='destination',
            name='summarize_recorded',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='destination',
            name='sentiment_analysis',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='destination',
            name='destination_cid_number_prefix',
            field=models.CharField(blank=True, default='', max_length=64, verbose_name='Caller ID number prefix'),
        ),
        migrations.AddField(
            model_name='destination',
            name='fax_receive',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='destination',
            name='fax_station_id',
            field=models.CharField(blank=True, default='', max_length=128),
        ),
        migrations.AddField(
            model_name='destination',
            name='fax_header',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='destination',
            name='fax_protocol',
            field=models.CharField(
                blank=True, default='t38_only', max_length=32,
                choices=[('t38_only', 'T.38 Only'), ('t38_preferred', 'T.38 Preferred'), ('sdp_passthrough', 'SDP Passthrough'), ('none', 'None')],
            ),
        ),
        migrations.AddField(
            model_name='destination',
            name='fax_email_destinations',
            field=models.CharField(blank=True, default='', help_text='Comma-separated emails for received faxes.', max_length=255),
        ),
        migrations.AddField(
            model_name='destination',
            name='fax_store',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='destination',
            name='fax_on_receive',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
    ]
