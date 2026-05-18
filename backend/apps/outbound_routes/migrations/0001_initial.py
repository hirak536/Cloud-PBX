import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('core', '0002_add_tenant'),
        ('gateways', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='OutboundRoute',
            fields=[
                ('outbound_route_uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('outbound_route_name', models.CharField(help_text='Human-readable label (e.g. Local Calls)', max_length=64)),
                ('outbound_route_order', models.IntegerField(default=10, help_text='Priority — lower numbers are matched first.')),
                ('dialplan_pattern', models.CharField(help_text='Regex matched against the dialed number. Use a capture group for the part to send, e.g. ^9(\\d{10})$', max_length=128)),
                ('prepend', models.CharField(blank=True, default='', help_text='Digits to prepend before the captured number when bridging, e.g. "1".', max_length=32)),
                ('outbound_route_enabled', models.BooleanField(default=True)),
                ('outbound_route_description', models.TextField(blank=True, default='')),
                ('insert_date', models.DateTimeField(auto_now_add=True, null=True)),
                ('insert_user', models.UUIDField(blank=True, null=True)),
                ('update_date', models.DateTimeField(auto_now=True, null=True)),
                ('update_user', models.UUIDField(blank=True, null=True)),
                ('domain', models.ForeignKey(blank=True, db_column='domain_uuid', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='outbound_routes', to='core.domain')),
                ('gateway', models.ForeignKey(blank=True, db_column='gateway_uuid', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='outbound_routes', to='gateways.gateway', verbose_name='Gateway')),
                ('gateway_2', models.ForeignKey(blank=True, db_column='gateway_2_uuid', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='outbound_routes_failover_1', to='gateways.gateway', verbose_name='Failover gateway')),
                ('gateway_3', models.ForeignKey(blank=True, db_column='gateway_3_uuid', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='outbound_routes_failover_2', to='gateways.gateway', verbose_name='2nd failover gateway')),
                ('tenant', models.ForeignKey(blank=True, db_column='tenant_uuid', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='outbound_routes_outboundroute_set', to='core.tenant')),
            ],
            options={
                'db_table': 'v_outbound_routes',
                'ordering': ['outbound_route_order', 'outbound_route_name'],
            },
        ),
        migrations.AddConstraint(
            model_name='outboundroute',
            constraint=models.UniqueConstraint(fields=['tenant', 'outbound_route_name'], name='unique_outbound_route_per_tenant'),
        ),
    ]
