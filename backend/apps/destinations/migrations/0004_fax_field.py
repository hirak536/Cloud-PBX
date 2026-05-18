"""Add fax FK to Destination for CNG auto-detection and fax-only DID routing."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('destinations', '0003_did_routing_redesign'),
        ('fax', '0001_initial'),
    ]

    operations = [
        # Update dest_type choices to include 'fax'
        migrations.AlterField(
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
                    ('fax', 'Fax (direct fax receive)'),
                    ('hangup', 'Hangup'),
                ],
                default='extension',
                max_length=32,
                verbose_name='Destination type',
            ),
        ),
        # Add FK to Fax model
        migrations.AddField(
            model_name='destination',
            name='fax',
            field=models.ForeignKey(
                blank=True,
                db_column='fax_uuid',
                help_text=(
                    'Link a fax box for two use cases: '
                    '(1) Set Destination type = "Fax" to route all calls directly to this fax box. '
                    '(2) Set any other Destination type + select a Fax box here to enable CNG '
                    'auto-detection — voice calls route normally, fax calls auto-switch to the fax box.'
                ),
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='destinations',
                to='fax.fax',
                verbose_name='Fax box',
            ),
        ),
    ]
