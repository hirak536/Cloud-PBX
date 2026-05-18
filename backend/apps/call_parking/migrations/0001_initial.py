import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CallParkingSlot',
            fields=[
                ('call_parking_slot_uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('slot_number', models.IntegerField()),
                ('slot_name', models.CharField(blank=True, default='', max_length=128)),
                ('parking_timeout', models.IntegerField(default=60)),
                ('timeout_action', models.CharField(
                    choices=[
                        ('hangup', 'Hangup'),
                        ('return_to_parker', 'Return to Parker'),
                        ('voicemail', 'Send to Voicemail'),
                    ],
                    default='hangup',
                    max_length=32,
                )),
                ('timeout_voicemail_extension', models.CharField(blank=True, default='', max_length=32)),
                ('music_on_hold', models.CharField(blank=True, default='', max_length=255)),
                ('slot_enabled', models.BooleanField(default=True)),
                ('insert_date', models.DateTimeField(auto_now_add=True, null=True)),
                ('insert_user', models.UUIDField(blank=True, null=True)),
                ('update_date', models.DateTimeField(auto_now=True, null=True)),
                ('update_user', models.UUIDField(blank=True, null=True)),
                ('domain', models.ForeignKey(
                    db_column='domain_uuid',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='call_parking_slots',
                    to='core.domain',
                )),
                ('tenant', models.ForeignKey(
                    blank=True,
                    db_column='tenant_uuid',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='call_parking_callparkingslot_set',
                    to='core.tenant',
                )),
            ],
            options={
                'db_table': 'v_call_parking_slots',
                'unique_together': {('tenant', 'slot_number')},
            },
        ),
    ]
