import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('core', '0003_fix_fk_related_names'),
    ]

    operations = [
        migrations.CreateModel(
            name='WorkingHours',
            fields=[
                ('working_hours_uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('working_hours_name', models.CharField(max_length=255)),
                ('working_hours_description', models.TextField(blank=True)),
                ('working_hours_enabled', models.BooleanField(default=True)),
                ('dialplan_extension', models.CharField(blank=True, help_text='Dialplan extension matched by FreeSWITCH (e.g. wh_a1b2c3d4). Auto-generated if blank.', max_length=255)),
                ('timezone', models.CharField(default='UTC', help_text='Timezone for display purposes. FreeSWITCH uses the server timezone.', max_length=64)),
                ('open_dest_type', models.CharField(choices=[('extension', 'Extension'), ('ring_group', 'Ring Group'), ('voicemail', 'Voicemail'), ('ivr_menu', 'IVR Menu'), ('conference', 'Conference'), ('external', 'External Number'), ('hangup', 'Hangup')], default='hangup', help_text='Where to route calls during open hours.', max_length=64)),
                ('open_dest_target_uuid', models.UUIDField(blank=True, help_text='UUID of the open-hours destination object (Extension, Ring Group, etc.).', null=True)),
                ('open_dest_external_number', models.CharField(blank=True, help_text='External number for open-hours routing (used when dest_type=external).', max_length=255)),
                ('closed_dest_type', models.CharField(choices=[('extension', 'Extension'), ('ring_group', 'Ring Group'), ('voicemail', 'Voicemail'), ('ivr_menu', 'IVR Menu'), ('conference', 'Conference'), ('external', 'External Number'), ('hangup', 'Hangup')], default='hangup', help_text='Where to route calls outside open hours.', max_length=64)),
                ('closed_dest_target_uuid', models.UUIDField(blank=True, help_text='UUID of the closed-hours destination object.', null=True)),
                ('closed_dest_external_number', models.CharField(blank=True, help_text='External number for closed-hours routing (used when dest_type=external).', max_length=255)),
                ('insert_date', models.DateTimeField(auto_now_add=True)),
                ('insert_user', models.UUIDField(blank=True, null=True)),
                ('update_date', models.DateTimeField(auto_now=True)),
                ('update_user', models.UUIDField(blank=True, null=True)),
                ('domain', models.ForeignKey(blank=True, db_column='domain_uuid', null=True, on_delete=django.db.models.deletion.CASCADE, to='core.domain')),
                ('tenant', models.ForeignKey(blank=True, db_column='tenant_uuid', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_set', to='core.tenant')),
            ],
            options={
                'db_table': 'v_working_hours',
            },
        ),
        migrations.CreateModel(
            name='WorkingHoursDay',
            fields=[
                ('day_uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('day_of_week', models.IntegerField(choices=[(1, 'Monday'), (2, 'Tuesday'), (3, 'Wednesday'), (4, 'Thursday'), (5, 'Friday'), (6, 'Saturday'), (7, 'Sunday')], help_text='1=Monday, 7=Sunday.')),
                ('is_open', models.BooleanField(default=True, help_text='Whether this is a working day.')),
                ('open_time', models.TimeField(blank=True, help_text='Start of working hours (e.g. 09:00).', null=True)),
                ('close_time', models.TimeField(blank=True, help_text='End of working hours (e.g. 17:00).', null=True)),
                ('tenant', models.ForeignKey(blank=True, db_column='tenant_uuid', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_set', to='core.tenant')),
                ('working_hours', models.ForeignKey(db_column='working_hours_uuid', on_delete=django.db.models.deletion.CASCADE, related_name='days', to='working_hours.workinghours')),
            ],
            options={
                'db_table': 'v_working_hours_days',
                'ordering': ['day_of_week'],
            },
        ),
        migrations.AddConstraint(
            model_name='workinghoursday',
            constraint=models.UniqueConstraint(fields=['working_hours', 'day_of_week'], name='unique_working_hours_day'),
        ),
        migrations.CreateModel(
            name='WorkingHoursHoliday',
            fields=[
                ('holiday_uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('holiday_date', models.DateField(help_text='Date of the holiday (YYYY-MM-DD).')),
                ('holiday_name', models.CharField(blank=True, max_length=255)),
                ('tenant', models.ForeignKey(blank=True, db_column='tenant_uuid', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_set', to='core.tenant')),
                ('working_hours', models.ForeignKey(db_column='working_hours_uuid', on_delete=django.db.models.deletion.CASCADE, related_name='holidays', to='working_hours.workinghours')),
            ],
            options={
                'db_table': 'v_working_hours_holidays',
                'ordering': ['holiday_date'],
            },
        ),
    ]
