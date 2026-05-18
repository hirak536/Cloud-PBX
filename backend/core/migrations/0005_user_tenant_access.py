import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_add_tenant_code_autogen_and_domain_universal'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserTenantAccess',
            fields=[
                ('user_tenant_access_uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('insert_date', models.DateTimeField(auto_now_add=True, null=True)),
                ('user', models.ForeignKey(
                    db_column='user_uuid',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='tenant_accesses',
                    to='core.user',
                    to_field='user_uuid',
                )),
                ('tenant', models.ForeignKey(
                    db_column='tenant_uuid',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='admin_accesses',
                    to='core.tenant',
                    to_field='tenant_uuid',
                )),
            ],
            options={
                'db_table': 'v_user_tenant_access',
                'unique_together': {('user', 'tenant')},
            },
        ),
        migrations.AddField(
            model_name='user',
            name='admin_tenants',
            field=models.ManyToManyField(
                blank=True,
                related_name='admin_users',
                through='core.UserTenantAccess',
                to='core.tenant',
            ),
        ),
    ]
