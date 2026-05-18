"""Development settings."""
from .base import *

DEBUG = True
ALLOWED_HOSTS = ['*']

# EMAIL_BACKEND is read from .env (defaults to console for local dev)
# Set EMAIL_BACKEND=apps.common.email_backend.DatabaseEmailBackend in .env for production-like email

# DRF - allow browsable API in dev
REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] = [
    'rest_framework.renderers.JSONRenderer',
    'rest_framework.renderers.BrowsableAPIRenderer',
]

# Disable HTTPS requirements in dev
SECURE_CONTENT_TYPE_NOSNIFF = False
SESSION_COOKIE_SECURE = False

# Logging - more verbose in dev
LOGGING['root']['level'] = 'DEBUG'
LOGGING['handlers']['console']['formatter'] = 'simple'
