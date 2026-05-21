import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()
from apps.extensions.models import Extension

for code in ['901', '906', '908']:
    try:
        e = Extension.objects.get(tenant__tenant_code='IHDT', extension=code)
        print(f"\n=== {code} ===")
        print(f"  transport: {e.transport}")
        print(f"  webrtc_support: {e.webrtc_support}")
        print(f"  rtp_encryption: {e.rtp_encryption}")
        print(f"  sip_bypass_media: {e.sip_bypass_media!r}")
        print(f"  codec_preference: {e.codec_preference!r}")
    except Extension.DoesNotExist:
        print(f"{code}: not found")
