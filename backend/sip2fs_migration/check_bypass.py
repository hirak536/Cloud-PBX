import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.dev'
django.setup()
from apps.sip_profiles.models import SipProfile

for p in SipProfile.objects.all():
    print(f'Profile: {p.sip_profile_name}')
    for s in p.settings.all():
        if 'bypass' in s.sip_profile_setting_name.lower() or 'proxy' in s.sip_profile_setting_name.lower() or 'srtp' in s.sip_profile_setting_name.lower():
            print(f'  {s.sip_profile_setting_name} = {s.sip_profile_setting_value}')
    print()
