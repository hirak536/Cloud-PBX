from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gateways', '0002_add_tenant'),
    ]

    operations = [
        migrations.AddField(
            model_name='gateway',
            name='trunk_type',
            field=models.CharField(
                choices=[
                    ('register', 'Register — PBX registers to provider (username/password)'),
                    ('account',  'Account — Digest auth on outbound, no registration'),
                    ('peer',     'Peer — IP-based auth, no credentials required'),
                ],
                default='register',
                help_text='How FreeSWITCH authenticates with this trunk.',
                max_length=16,
            ),
        ),
    ]
