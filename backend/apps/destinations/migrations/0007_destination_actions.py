import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('destinations', '0006_did_extended_fields'),
    ]

    operations = [
        # Allow dest_type to be blank (it is now synced from first action)
        migrations.AlterField(
            model_name='destination',
            name='dest_type',
            field=models.CharField(
                blank=True, default='', max_length=32,
                choices=[
                    ('extension',      'Extension'),
                    ('ivr_menu',       'IVR Menu'),
                    ('ring_group',     'Ring Group'),
                    ('voicemail',      'Voicemail'),
                    ('time_condition', 'Time Condition'),
                    ('working_hours',  'Working Hours'),
                    ('call_flow',      'Call Flow'),
                    ('conference',     'Conference'),
                    ('external',       'External Number'),
                    ('fax',            'Fax (direct fax receive)'),
                    ('hangup',         'Hangup'),
                ],
                verbose_name='Destination type (synced from first action)',
            ),
        ),
        # Create the ordered-actions table
        migrations.CreateModel(
            name='DestinationAction',
            fields=[
                ('destination_action_uuid', models.UUIDField(
                    primary_key=True, default=uuid.uuid4, editable=False, serialize=False,
                )),
                ('destination', models.ForeignKey(
                    db_column='destination_uuid',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='actions',
                    to='destinations.destination',
                )),
                ('dest_type', models.CharField(
                    max_length=32,
                    choices=[
                        ('extension',      'Extension'),
                        ('ivr_menu',       'IVR Menu'),
                        ('ring_group',     'Ring Group'),
                        ('voicemail',      'Voicemail'),
                        ('time_condition', 'Time Condition'),
                        ('working_hours',  'Working Hours'),
                        ('call_flow',      'Call Flow'),
                        ('conference',     'Conference'),
                        ('external',       'External Number'),
                        ('fax',            'Fax (direct fax receive)'),
                        ('hangup',         'Hangup'),
                    ],
                )),
                ('dest_target_uuid', models.UUIDField(null=True, blank=True)),
                ('dest_external_number', models.CharField(blank=True, default='', max_length=64)),
                ('order', models.PositiveSmallIntegerField(default=0)),
            ],
            options={
                'db_table': 'v_destination_actions',
                'ordering': ['order'],
            },
        ),
    ]
