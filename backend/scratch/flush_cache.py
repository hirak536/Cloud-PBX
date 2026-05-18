import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core.cache import cache

try:
    # If using Redis with delete_pattern support (django-redis)
    cache.delete_pattern('dialplan:xml:*')
    print('Flushed dialplan:xml:*')
except Exception:
    # Fallback to full clear if delete_pattern not available
    cache.clear()
    print('Cache cleared completely')
