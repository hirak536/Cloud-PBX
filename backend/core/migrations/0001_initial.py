import uuid
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Domain',
            fields=[
                ('domain_uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('domain_name', models.CharField(max_length=128, unique=True)),
                ('domain_parent_uuid', models.UUIDField(blank=True, null=True)),
                ('domain_enabled', models.BooleanField(default=True)),
                ('domain_description', models.TextField(blank=True, default='')),
                ('insert_date', models.DateTimeField(auto_now_add=True, null=True)),
                ('insert_user', models.UUIDField(blank=True, null=True)),
                ('update_date', models.DateTimeField(auto_now=True, null=True)),
                ('update_user', models.UUIDField(blank=True, null=True)),
            ],
            options={'db_table': 'v_domains'},
        ),
        migrations.CreateModel(
            name='DefaultSetting',
            fields=[
                ('default_setting_uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('app_uuid', models.UUIDField(blank=True, null=True)),
                ('default_setting_category', models.CharField(max_length=128)),
                ('default_setting_subcategory', models.CharField(blank=True, default='', max_length=256)),
                ('default_setting_name', models.CharField(default='text', max_length=64)),
                ('default_setting_value', models.TextField(blank=True, default='')),
                ('default_setting_order', models.IntegerField(default=0)),
                ('default_setting_enabled', models.BooleanField(default=True)),
                ('default_setting_description', models.TextField(blank=True, default='')),
                ('insert_date', models.DateTimeField(auto_now_add=True, null=True)),
                ('insert_user', models.UUIDField(blank=True, null=True)),
                ('update_date', models.DateTimeField(auto_now=True, null=True)),
                ('update_user', models.UUIDField(blank=True, null=True)),
            ],
            options={'db_table': 'v_default_settings'},
        ),
        migrations.CreateModel(
            name='Permission',
            fields=[
                ('permission_uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('permission_name', models.CharField(max_length=128, unique=True)),
                ('permission_description', models.TextField(blank=True, default='')),
            ],
            options={'db_table': 'v_permissions'},
        ),
        migrations.CreateModel(
            name='User',
            fields=[
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('user_uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('username', models.CharField(max_length=254)),
                ('user_enabled', models.BooleanField(default=True)),
                ('user_status', models.CharField(blank=True, default='', max_length=32)),
                ('user_email', models.EmailField(blank=True, default='', max_length=254)),
                ('user_totp_secret', models.CharField(blank=True, default='', max_length=64)),
                ('api_key', models.CharField(blank=True, db_index=True, default='', max_length=128)),
                ('is_staff', models.BooleanField(default=False)),
                ('is_superuser', models.BooleanField(default=False)),
                ('insert_date', models.DateTimeField(auto_now_add=True, null=True)),
                ('insert_user', models.UUIDField(blank=True, null=True)),
                ('update_date', models.DateTimeField(auto_now=True, null=True)),
                ('update_user', models.UUIDField(blank=True, null=True)),
                ('domain', models.ForeignKey(
                    blank=True, db_column='domain_uuid', null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='users', to='core.domain',
                )),
            ],
            options={'db_table': 'v_users'},
        ),
        migrations.AlterUniqueTogether(
            name='user',
            unique_together={('domain', 'username')},
        ),
        migrations.CreateModel(
            name='Group',
            fields=[
                ('group_uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('group_name', models.CharField(max_length=64)),
                ('group_level', models.IntegerField(default=0)),
                ('group_protected', models.BooleanField(default=False)),
                ('group_description', models.TextField(blank=True, default='')),
                ('insert_date', models.DateTimeField(auto_now_add=True, null=True)),
                ('insert_user', models.UUIDField(blank=True, null=True)),
                ('update_date', models.DateTimeField(auto_now=True, null=True)),
                ('update_user', models.UUIDField(blank=True, null=True)),
                ('domain', models.ForeignKey(
                    blank=True, db_column='domain_uuid', null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='groups', to='core.domain',
                )),
            ],
            options={'db_table': 'v_groups'},
        ),
        migrations.AlterUniqueTogether(
            name='group',
            unique_together={('domain', 'group_name')},
        ),
        migrations.CreateModel(
            name='GroupPermission',
            fields=[
                ('group_permission_uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('permission_name', models.CharField(max_length=128)),
                ('permission_assigned', models.BooleanField(default=True)),
                ('insert_date', models.DateTimeField(auto_now_add=True, null=True)),
                ('insert_user', models.UUIDField(blank=True, null=True)),
                ('domain', models.ForeignKey(
                    blank=True, db_column='domain_uuid', null=True,
                    on_delete=django.db.models.deletion.CASCADE, to='core.domain',
                )),
                ('group', models.ForeignKey(
                    db_column='group_uuid', on_delete=django.db.models.deletion.CASCADE,
                    related_name='permissions', to='core.group', to_field='group_uuid',
                )),
            ],
            options={'db_table': 'v_group_permissions'},
        ),
        migrations.AlterUniqueTogether(
            name='grouppermission',
            unique_together={('domain', 'group', 'permission_name')},
        ),
        migrations.CreateModel(
            name='UserGroup',
            fields=[
                ('user_group_uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('insert_date', models.DateTimeField(auto_now_add=True, null=True)),
                ('domain', models.ForeignKey(
                    blank=True, db_column='domain_uuid', null=True,
                    on_delete=django.db.models.deletion.CASCADE, to='core.domain',
                )),
                ('group', models.ForeignKey(
                    db_column='group_uuid', on_delete=django.db.models.deletion.CASCADE,
                    related_name='user_groups', to='core.group', to_field='group_uuid',
                )),
                ('user', models.ForeignKey(
                    db_column='user_uuid', on_delete=django.db.models.deletion.CASCADE,
                    related_name='user_groups', to=settings.AUTH_USER_MODEL, to_field='user_uuid',
                )),
            ],
            options={'db_table': 'v_user_groups'},
        ),
        migrations.AlterUniqueTogether(
            name='usergroup',
            unique_together={('user', 'group')},
        ),
        migrations.CreateModel(
            name='DomainSetting',
            fields=[
                ('domain_setting_uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('app_uuid', models.UUIDField(blank=True, null=True)),
                ('domain_setting_category', models.CharField(max_length=128)),
                ('domain_setting_subcategory', models.CharField(blank=True, default='', max_length=256)),
                ('domain_setting_name', models.CharField(default='text', max_length=64)),
                ('domain_setting_value', models.TextField(blank=True, default='')),
                ('domain_setting_order', models.IntegerField(default=0)),
                ('domain_setting_enabled', models.BooleanField(default=True)),
                ('domain_setting_description', models.TextField(blank=True, default='')),
                ('insert_date', models.DateTimeField(auto_now_add=True, null=True)),
                ('insert_user', models.UUIDField(blank=True, null=True)),
                ('update_date', models.DateTimeField(auto_now=True, null=True)),
                ('update_user', models.UUIDField(blank=True, null=True)),
                ('domain', models.ForeignKey(
                    db_column='domain_uuid', on_delete=django.db.models.deletion.CASCADE,
                    related_name='settings', to='core.domain',
                )),
            ],
            options={'db_table': 'v_domain_settings'},
        ),
        migrations.CreateModel(
            name='UserSetting',
            fields=[
                ('user_setting_uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('user_setting_category', models.CharField(max_length=128)),
                ('user_setting_subcategory', models.CharField(blank=True, default='', max_length=256)),
                ('user_setting_name', models.CharField(default='text', max_length=64)),
                ('user_setting_value', models.TextField(blank=True, default='')),
                ('user_setting_order', models.IntegerField(default=0)),
                ('user_setting_enabled', models.BooleanField(default=True)),
                ('user_setting_description', models.TextField(blank=True, default='')),
                ('insert_date', models.DateTimeField(auto_now_add=True, null=True)),
                ('domain', models.ForeignKey(
                    db_column='domain_uuid', null=True,
                    on_delete=django.db.models.deletion.CASCADE, to='core.domain',
                )),
                ('user', models.ForeignKey(
                    db_column='user_uuid', on_delete=django.db.models.deletion.CASCADE,
                    related_name='settings', to=settings.AUTH_USER_MODEL, to_field='user_uuid',
                )),
            ],
            options={'db_table': 'v_user_settings'},
        ),
        migrations.CreateModel(
            name='UserLog',
            fields=[
                ('user_log_uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('username', models.CharField(blank=True, default='', max_length=254)),
                ('user_log_type', models.CharField(
                    choices=[('login', 'Login'), ('logout', 'Logout'), ('failed', 'Failed Login'), ('session', 'Session')],
                    default='login', max_length=32,
                )),
                ('user_log_ipv4', models.GenericIPAddressField(blank=True, null=True, protocol='IPv4')),
                ('user_log_agent', models.TextField(blank=True, default='')),
                ('user_log_timestamp', models.DateTimeField(default=django.utils.timezone.now)),
                ('user_log_message', models.TextField(blank=True, default='')),
                ('domain', models.ForeignKey(
                    db_column='domain_uuid', null=True,
                    on_delete=django.db.models.deletion.SET_NULL, to='core.domain',
                )),
                ('user', models.ForeignKey(
                    db_column='user_uuid', null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='logs', to=settings.AUTH_USER_MODEL, to_field='user_uuid',
                )),
            ],
            options={'db_table': 'v_user_logs', 'ordering': ['-user_log_timestamp']},
        ),
        migrations.CreateModel(
            name='DomainLimit',
            fields=[
                ('domain_limit_uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('domain_limit_name', models.CharField(max_length=128)),
                ('domain_limit_value', models.TextField(blank=True, default='')),
                ('domain_limit_enabled', models.BooleanField(default=True)),
                ('domain_limit_description', models.TextField(blank=True, default='')),
                ('domain', models.ForeignKey(
                    db_column='domain_uuid', on_delete=django.db.models.deletion.CASCADE,
                    related_name='limits', to='core.domain',
                )),
            ],
            options={'db_table': 'v_domain_limits'},
        ),
    ]
