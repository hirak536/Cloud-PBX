"""
Redesign Destination model for clean DID management.

Adds high-level destination routing fields (dest_type, dest_target_uuid,
dest_external_number) and removes the low-level raw dialplan fields that
were replaced by the auto-generated dialplan in generators.py.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('destinations', '0002_add_tenant'),
    ]

    operations = [
        # ── Add new DID routing fields ────────────────────────────────────
        migrations.AddField(
            model_name='destination',
            name='dest_type',
            field=models.CharField(
                choices=[
                    ('extension', 'Extension'),
                    ('ivr_menu', 'IVR Menu'),
                    ('ring_group', 'Ring Group'),
                    ('voicemail', 'Voicemail'),
                    ('time_condition', 'Time Condition'),
                    ('call_flow', 'Call Flow'),
                    ('conference', 'Conference'),
                    ('external', 'External Number'),
                    ('hangup', 'Hangup'),
                ],
                default='extension',
                max_length=32,
                verbose_name='Destination type',
            ),
        ),
        migrations.AddField(
            model_name='destination',
            name='dest_target_uuid',
            field=models.UUIDField(
                blank=True,
                null=True,
                verbose_name='Destination target',
                help_text='UUID of the Extension / IVR / Ring Group / etc.',
            ),
        ),
        migrations.AddField(
            model_name='destination',
            name='dest_external_number',
            field=models.CharField(
                blank=True,
                default='',
                max_length=64,
                verbose_name='External number',
                help_text='Phone number to bridge to (External Number type only).',
            ),
        ),

        # ── Clean up help text / verbose names on existing fields ─────────
        migrations.AlterField(
            model_name='destination',
            name='destination_number',
            field=models.CharField(
                max_length=64,
                help_text='DID / inbound phone number, e.g. +15551002000.',
            ),
        ),
        migrations.AlterField(
            model_name='destination',
            name='destination_cid_name_prefix',
            field=models.CharField(
                blank=True,
                default='',
                max_length=64,
                verbose_name='Caller ID name prefix',
                help_text='Text prepended to inbound caller ID name, e.g. "Sales: ".',
            ),
        ),

        # ── Remove old low-level dialplan fields ──────────────────────────
        migrations.RemoveField(model_name='destination', name='destination_type'),
        migrations.RemoveField(model_name='destination', name='dialplan_uuid'),
        migrations.RemoveField(model_name='destination', name='destination_context'),
        migrations.RemoveField(model_name='destination', name='destination_app'),
        migrations.RemoveField(model_name='destination', name='destination_data'),
        migrations.RemoveField(model_name='destination', name='destination_bridge'),
        migrations.RemoveField(model_name='destination', name='destination_caller_id_name'),
        migrations.RemoveField(model_name='destination', name='destination_caller_id_number'),
    ]
