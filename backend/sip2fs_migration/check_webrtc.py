import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.dev'
django.setup()
from apps.extensions.models import Extension

for num in ['908', '929']:
    e = Extension.objects.filter(extension=num).first()
    if not e:
        print(f'{num}: NOT FOUND')
        continue
    tcode = e.tenant.tenant_code if e.tenant else '?'
    print(f'Ext {num} ({tcode}):')
    print(f'  transport               = {e.transport}')
    print(f'  webrtc_support          = {e.webrtc_support}')
    print(f'  rtp_encryption          = {e.rtp_encryption}')
    print(f'  sip_bypass_media        = {e.sip_bypass_media!r}')
    print(f'  sip_bypass_media_webrtc = {e.sip_bypass_media_webrtc!r}')
    print(f'  codec_preference        = {e.codec_preference!r}')
    print(f'  absolute_codec_string   = {e.absolute_codec_string!r}')
    print()
