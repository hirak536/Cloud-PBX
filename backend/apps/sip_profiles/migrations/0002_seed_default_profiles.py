from django.db import migrations


DEFAULT_PROFILES = [
    ('internal',      'Internal SIP profile (LAN extensions)'),
    ('external',      'External SIP profile (VoIP trunks / gateways)'),
    ('internal-ipv6', 'Internal SIP profile IPv6'),
    ('external-ipv6', 'External SIP profile IPv6'),
]


def seed_profiles(apps, schema_editor):
    SipProfile = apps.get_model('sip_profiles', 'SipProfile')
    for name, desc in DEFAULT_PROFILES:
        SipProfile.objects.get_or_create(
            sip_profile_name=name,
            defaults={'sip_profile_description': desc, 'sip_profile_enabled': True},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('sip_profiles', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_profiles, reverse_code=migrations.RunPython.noop),
    ]
