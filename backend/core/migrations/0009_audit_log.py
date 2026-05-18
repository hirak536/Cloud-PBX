from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_tenant_default_gateway_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='AuditLog',
            fields=[
                ('audit_log_uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('username', models.CharField(blank=True, default='', max_length=254)),
                ('action', models.CharField(choices=[('create', 'Create'), ('update', 'Update'), ('delete', 'Delete')], max_length=16)),
                ('resource_type', models.CharField(max_length=128)),
                ('resource_uuid', models.CharField(blank=True, default='', max_length=64)),
                ('resource_name', models.CharField(blank=True, default='', max_length=256)),
                ('changes', models.JSONField(blank=True, null=True)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True, protocol='IPv4')),
                ('user_agent', models.TextField(blank=True, default='')),
                ('timestamp', models.DateTimeField(default=django.utils.timezone.now)),
                ('domain', models.ForeignKey(blank=True, db_column='domain_uuid', null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.domain')),
                ('tenant', models.ForeignKey(blank=True, db_column='tenant_uuid', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='audit_logs', to='core.tenant')),
                ('user', models.ForeignKey(blank=True, db_column='user_uuid', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='audit_logs', to='core.user', to_field='user_uuid')),
            ],
            options={
                'db_table': 'v_audit_logs',
                'ordering': ['-timestamp'],
            },
        ),
    ]
