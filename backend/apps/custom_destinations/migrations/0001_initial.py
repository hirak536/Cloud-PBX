from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('core', '0007_user_full_name_must_change_password'),
    ]

    operations = [
        migrations.CreateModel(
            name='CustomDestination',
            fields=[
                ('custom_destination_uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(help_text='Friendly name, e.g. "After Hours Voicemail".', max_length=128)),
                ('description', models.TextField(blank=True, default='')),
                ('dest_type', models.CharField(choices=[('extension', 'Extension'), ('ivr_menu', 'IVR Menu'), ('ring_group', 'Ring Group'), ('voicemail', 'Voicemail'), ('time_condition', 'Time Condition'), ('working_hours', 'Working Hours'), ('call_flow', 'Call Flow'), ('conference', 'Conference'), ('external', 'External Number'), ('fax', 'Fax'), ('hangup', 'Hangup')], max_length=32)),
                ('dest_target_uuid', models.UUIDField(blank=True, help_text='UUID of the Extension / IVR / Ring Group / etc.', null=True)),
                ('dest_external_number', models.CharField(blank=True, default='', help_text='External number (only used when dest_type = external).', max_length=64)),
                ('enabled', models.BooleanField(default=True)),
                ('insert_date', models.DateTimeField(auto_now_add=True)),
                ('insert_user', models.UUIDField(blank=True, null=True)),
                ('update_date', models.DateTimeField(auto_now=True)),
                ('update_user', models.UUIDField(blank=True, null=True)),
                ('domain', models.ForeignKey(blank=True, db_column='domain_uuid', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='custom_destinations', to='core.domain')),
                ('tenant', models.ForeignKey(blank=True, db_column='tenant_uuid', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='custom_destinations_customdestination_set', to='core.tenant')),
            ],
            options={
                'db_table': 'v_custom_destinations',
                'ordering': ['name'],
            },
        ),
    ]
