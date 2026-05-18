import uuid
import django.db.models.deletion
from django.db import migrations, models


def backfill_tenant_from_domain(apps, schema_editor):
    """
    Create one Tenant per Domain, then link all core objects.
    tenant_code is derived from the first label of domain_name (e.g. 'example' from 'example.com').
    """
    Domain = apps.get_model('core', 'Domain')
    Tenant = apps.get_model('core', 'Tenant')
    User = apps.get_model('core', 'User')
    Group = apps.get_model('core', 'Group')
    GroupPermission = apps.get_model('core', 'GroupPermission')
    UserGroup = apps.get_model('core', 'UserGroup')
    UserSetting = apps.get_model('core', 'UserSetting')
    UserLog = apps.get_model('core', 'UserLog')
    DomainLimit = apps.get_model('core', 'DomainLimit')

    domain_to_tenant = {}

    for domain in Domain.objects.all():
        raw_code = domain.domain_name.split('.')[0][:32]
        # Ensure uniqueness by appending suffix if needed
        code = raw_code
        suffix = 1
        while Tenant.objects.filter(tenant_code=code).exists():
            code = f'{raw_code}{suffix}'
            suffix += 1

        tenant = Tenant.objects.create(
            tenant_code=code,
            tenant_name=domain.domain_name,
            tenant_enabled=domain.domain_enabled,
        )
        domain.tenant = tenant
        domain.save(update_fields=['tenant_id'])
        domain_to_tenant[domain.pk] = tenant

    # Backfill User.tenant from user.domain.tenant
    for user in User.objects.select_related('domain').filter(domain__isnull=False):
        tenant = domain_to_tenant.get(user.domain_id)
        if tenant:
            user.tenant = tenant
            user.save(update_fields=['tenant_id'])

    # Backfill Group.tenant
    for obj in Group.objects.select_related('domain').filter(domain__isnull=False):
        tenant = domain_to_tenant.get(obj.domain_id)
        if tenant:
            obj.tenant = tenant
            obj.save(update_fields=['tenant_id'])

    # Backfill GroupPermission.tenant
    for obj in GroupPermission.objects.select_related('domain').filter(domain__isnull=False):
        tenant = domain_to_tenant.get(obj.domain_id)
        if tenant:
            obj.tenant = tenant
            obj.save(update_fields=['tenant_id'])

    # Backfill UserGroup.tenant
    for obj in UserGroup.objects.select_related('domain').filter(domain__isnull=False):
        tenant = domain_to_tenant.get(obj.domain_id)
        if tenant:
            obj.tenant = tenant
            obj.save(update_fields=['tenant_id'])

    # Backfill UserSetting.tenant
    for obj in UserSetting.objects.select_related('domain').filter(domain__isnull=False):
        tenant = domain_to_tenant.get(obj.domain_id)
        if tenant:
            obj.tenant = tenant
            obj.save(update_fields=['tenant_id'])

    # Backfill UserLog.tenant
    for obj in UserLog.objects.select_related('domain').filter(domain__isnull=False):
        tenant = domain_to_tenant.get(obj.domain_id)
        if tenant:
            obj.tenant = tenant
            obj.save(update_fields=['tenant_id'])

    # Backfill DomainLimit.tenant
    for obj in DomainLimit.objects.select_related('domain').filter(domain__isnull=False):
        tenant = domain_to_tenant.get(obj.domain_id)
        if tenant:
            obj.tenant = tenant
            obj.save(update_fields=['tenant_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        # 1. Create the Tenant model
        migrations.CreateModel(
            name='Tenant',
            fields=[
                ('tenant_uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('tenant_code', models.CharField(
                    help_text='Short alphanumeric code used as username prefix.',
                    max_length=32, unique=True,
                )),
                ('tenant_name', models.CharField(max_length=128)),
                ('tenant_enabled', models.BooleanField(default=True)),
                ('tenant_status', models.CharField(
                    choices=[('active', 'Active'), ('suspended', 'Suspended'), ('expired', 'Expired')],
                    default='active', max_length=16,
                )),
                ('expiration_date', models.DateField(blank=True, null=True)),
                ('max_channels', models.IntegerField(blank=True, null=True)),
                ('max_extensions', models.IntegerField(blank=True, null=True)),
                ('max_dids', models.IntegerField(blank=True, null=True)),
                ('billing_code', models.CharField(blank=True, default='', max_length=64)),
                ('payment_type', models.CharField(
                    choices=[('prepaid', 'Prepaid'), ('postpaid', 'Postpaid')],
                    default='postpaid', max_length=16,
                )),
                ('timezone', models.CharField(default='UTC', max_length=64)),
                ('allow_onnet_calls_from', models.BooleanField(default=True)),
                ('allow_onnet_calls_to', models.BooleanField(default=True)),
                ('recording_enabled', models.BooleanField(default=True)),
                ('provisioning_hostname', models.CharField(blank=True, default='', max_length=256)),
                ('description', models.TextField(blank=True, default='')),
                ('insert_date', models.DateTimeField(auto_now_add=True, null=True)),
                ('insert_user', models.UUIDField(blank=True, null=True)),
                ('update_date', models.DateTimeField(auto_now=True, null=True)),
                ('update_user', models.UUIDField(blank=True, null=True)),
            ],
            options={'db_table': 'v_tenants'},
        ),

        # 2. Add tenant FK to Domain
        migrations.AddField(
            model_name='domain',
            name='tenant',
            field=models.ForeignKey(
                blank=True, db_column='tenant_uuid', null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='domains', to='core.tenant',
            ),
        ),

        # 3. Add tenant FK to User
        migrations.AddField(
            model_name='user',
            name='tenant',
            field=models.ForeignKey(
                blank=True, db_column='tenant_uuid', null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='users', to='core.tenant',
            ),
        ),

        # 4. Add tenant FK to Group
        migrations.AddField(
            model_name='group',
            name='tenant',
            field=models.ForeignKey(
                blank=True, db_column='tenant_uuid', null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='groups', to='core.tenant',
            ),
        ),

        # 5. Add tenant FK to GroupPermission
        migrations.AddField(
            model_name='grouppermission',
            name='tenant',
            field=models.ForeignKey(
                blank=True, db_column='tenant_uuid', null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='group_permissions', to='core.tenant',
            ),
        ),

        # 6. Add tenant FK to UserGroup
        migrations.AddField(
            model_name='usergroup',
            name='tenant',
            field=models.ForeignKey(
                blank=True, db_column='tenant_uuid', null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='user_groups', to='core.tenant',
            ),
        ),

        # 7. Add tenant FK to UserSetting
        migrations.AddField(
            model_name='usersetting',
            name='tenant',
            field=models.ForeignKey(
                blank=True, db_column='tenant_uuid', null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='user_settings', to='core.tenant',
            ),
        ),

        # 8. Add tenant FK to UserLog
        migrations.AddField(
            model_name='userlog',
            name='tenant',
            field=models.ForeignKey(
                blank=True, db_column='tenant_uuid', null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='user_logs', to='core.tenant',
            ),
        ),

        # 9. Add tenant FK to DomainLimit
        migrations.AddField(
            model_name='domainlimit',
            name='tenant',
            field=models.ForeignKey(
                blank=True, db_column='tenant_uuid', null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='domain_limits', to='core.tenant',
            ),
        ),

        # 10. Update unique_together for Group (domain -> tenant)
        migrations.AlterUniqueTogether(
            name='group',
            unique_together={('tenant', 'group_name')},
        ),

        # 11. Update unique_together for GroupPermission (domain -> tenant)
        migrations.AlterUniqueTogether(
            name='grouppermission',
            unique_together={('tenant', 'group', 'permission_name')},
        ),

        # 12. Update unique_together for User (domain -> tenant)
        migrations.AlterUniqueTogether(
            name='user',
            unique_together={('tenant', 'username')},
        ),

        # 13. Backfill tenant references for existing data
        migrations.RunPython(
            backfill_tenant_from_domain,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
