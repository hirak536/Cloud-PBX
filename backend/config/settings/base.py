"""
Base Django settings for IHS PBX - shared across all environments.
"""
import os
from pathlib import Path
from datetime import timedelta
from decouple import config, Csv

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Security
SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', cast=Csv())
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', cast=Csv())

# Public-facing base URL used to build absolute URLs (e.g. in webhook payloads)
# e.g. https://fs.ihsclients.com
PUBLIC_BASE_URL = config('PUBLIC_BASE_URL', default='https://fs.ihsclients.com')

# Application definition
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',
    'channels',
    'django_otp',
    'django_otp.plugins.otp_totp',
    'django_otp.plugins.otp_static',
    'django_celery_beat',
    'django_celery_results',
    'drf_spectacular',
]

LOCAL_APPS = [
    'core',
    'esl',
    'freeswitch_config.apps.FreeswitchConfigConfig',
    'apps.extensions',
    'apps.dialplans',
    'apps.voicemails',
    'apps.gateways',
    'apps.sip_profiles',
    'apps.call_centers',
    'apps.conferences',
    'apps.devices',
    'apps.provision',
    'apps.xml_cdr',
    'apps.recordings',
    'apps.ring_groups',
    'apps.ivr_menus',
    'apps.call_flows',
    'apps.time_conditions',
    'apps.destinations',
    'apps.feature_codes',
    'apps.access_controls',
    'apps.music_on_hold',
    'apps.fax',
    'apps.email_queue',
    'apps.number_translations',
    'apps.modules_app',
    'apps.pin_numbers',
    'apps.vars',
    'apps.follow_me',
    'apps.call_block',
    'apps.call_broadcast',
    'apps.fifo',
    'apps.emergency',
    'apps.event_guard',
    'apps.domain_limits',
    'apps.sofia_global_settings',
    'apps.voicemail_greetings',
    'apps.extension_settings',
    'apps.working_hours',
    'apps.outbound_routes',
    'apps.firewall',
    'apps.custom_destinations',
    'apps.call_parking',
    'apps.client_api',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_otp.middleware.OTPMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.TenantMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Database - PostgreSQL
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST'),
        'PORT': config('DB_PORT'),
        'CONN_MAX_AGE': 0,
        'OPTIONS': {
            'options': '-c search_path=public',
        },
    },
    'voicemail_sqlite': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': config('VOICEMAIL_SQLITE_PATH'),
        'OPTIONS': {
            'timeout': 5,
        },
    },
    # Separate database for call detail records (Phase 2 of CDR-DB separation).
    # CDRs live here so they can be backed up / purged on their own schedule and
    # so high CDR write volume doesn't contend with the app DB. Defaults to the
    # main DB's host/user/password; override CDR_DB_* in .env to relocate it.
    'cdr': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('CDR_DB_NAME', default='ihspbx_cdr'),
        'USER': config('CDR_DB_USER', default=config('DB_USER')),
        'PASSWORD': config('CDR_DB_PASSWORD', default=config('DB_PASSWORD')),
        'HOST': config('CDR_DB_HOST', default=config('DB_HOST')),
        'PORT': config('CDR_DB_PORT', default=config('DB_PORT')),
        'CONN_MAX_AGE': 0,
        'OPTIONS': {
            'options': '-c search_path=public',
        },
    },
}

DATABASE_ROUTERS = [
    'freeswitch_config.routers.VoicemailSQLiteRouter',
    'freeswitch_config.routers.CdrRouter',
]

# Custom User Model
AUTH_USER_MODEL = 'core.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Authentication backends
AUTHENTICATION_BACKENDS = [
    'core.authentication.DatabaseAuthBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = config('TIME_ZONE')
USE_I18N = True
USE_TZ = True

# Static & Media files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Serve built React frontend from root (assets, favicon, etc.)
WHITENOISE_ROOT = BASE_DIR.parent / 'frontend' / 'dist'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Redis
REDIS_URL = config('REDIS_URL')

# Channel layers (WebSocket via Redis)
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [REDIS_URL],
        },
    },
}

# Cache
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config('REDIS_CACHE_URL'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'TIMEOUT': 300,
    }
}

# Celery
CELERY_BROKER_URL = config('CELERY_BROKER_URL')
CELERY_RESULT_BACKEND = 'django-db'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

from celery.schedules import crontab
CELERY_BEAT_SCHEDULE = {
    'send-pending-emails-every-minute': {
        'task': 'email_queue.send_pending',
        'schedule': crontab(minute='*'),
    },
    'push-extension-status-every-5s': {
        'task': 'esl.tasks.push_extension_status_update',
        'schedule': 5.0,
    },
    'push-active-calls-every-5s': {
        'task': 'esl.tasks.push_active_calls_update',
        'schedule': 5.0,
    },
    'poll-peer-states-every-10s': {
        'task': 'esl.tasks.poll_peer_states',
        'schedule': 10.0,
    },
    'cleanup-peer-state-history-daily': {
        'task': 'esl.tasks.cleanup_peer_state_history',
        'schedule': crontab(hour=3, minute=15),
    },
    # Pre-slice recently-ended calls' SIP pcap off the ingest path, so the
    # SIP/PCAP viewer reads a tiny per-call file instead of scanning the large
    # rolling capture on every open. Runs every minute; never touches ingest.
    'slice-sip-pcaps-every-minute': {
        'task': 'apps.xml_cdr.tasks.sweep_unsliced_pcaps',
        'schedule': crontab(minute='*'),
    },
}

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'core.pagination.StandardPagination',
    'PAGE_SIZE': 25,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'EXCEPTION_HANDLER': 'core.exceptions.custom_exception_handler',
}

# JWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=config('JWT_ACCESS_MINUTES', cast=int)),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=config('JWT_REFRESH_DAYS', cast=int)),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': config('SECRET_KEY'),
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'user_uuid',
    'USER_ID_CLAIM': 'user_uuid',
}

# CORS
CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', cast=Csv())
CORS_ALLOW_CREDENTIALS = True

# API Documentation (drf-spectacular)
SPECTACULAR_SETTINGS = {
    'TITLE': 'IHS PBX API',
    'DESCRIPTION': 'Full-featured PBX management API backed by FreeSWITCH',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# Email
EMAIL_BACKEND = config('EMAIL_BACKEND')
EMAIL_HOST = config('EMAIL_HOST')
EMAIL_PORT = config('EMAIL_PORT', cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', cast=bool)
EMAIL_USE_SSL = config('EMAIL_USE_SSL', cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL')
FRONTEND_URL = config('FRONTEND_URL')

# FreeSWITCH ESL
FREESWITCH_HOST = config('FREESWITCH_HOST')
FREESWITCH_PORT = config('FREESWITCH_PORT', cast=int)
FREESWITCH_PASSWORD = config('FREESWITCH_PASSWORD')
FREESWITCH_TIMEOUT = config('FREESWITCH_TIMEOUT', cast=int)
AI_BRIDGE_WS = config('AI_BRIDGE_WS', default='ws://127.0.0.1:5001/audio')

# FreeSWITCH paths
FREESWITCH_CONF_DIR = config('FREESWITCH_CONF_DIR')
FREESWITCH_SOUNDS_DIR = config('FREESWITCH_SOUNDS_DIR')
FREESWITCH_GATEWAY_DIR = config('FREESWITCH_GATEWAY_DIR')
FREESWITCH_RECORDINGS_DIR = config('FREESWITCH_RECORDINGS_DIR')
FREESWITCH_VOICEMAIL_DIR = config('FREESWITCH_VOICEMAIL_DIR')

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': config('LOG_FILE'),
            'maxBytes': 10 * 1024 * 1024,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
            'delay': True,
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'esl': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        # FreeSWITCH XML cURL + CDR ingest — log at DEBUG so every dialplan
        # lookup, directory request, and CDR POST is captured to file.
        'freeswitch_config': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        # Voicemail tasks — log at DEBUG so every step of the transcription
        # and email flow (file resolution, attachment, SMTP) is captured.
        'apps.voicemails': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        # Fax tasks — log at DEBUG so every step of inbound delivery (TIFF→PDF
        # conversion, FTP connect/login/TLS/cwd/STOR, email) is captured.
        'apps.fax': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# Session
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_SAVE_EVERY_REQUEST = False
SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', cast=bool)
CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', cast=bool)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

# Security headers
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'

# PBX domain settings
PBX_DEFAULT_DOMAIN = config('PBX_DEFAULT_DOMAIN')

# Deepgram transcription
DEEPGRAM_API_KEY = config('DEEPGRAM_API_KEY', default='')

# Gemini transcription
GEMINI_API_KEY = config('GEMINI_API_KEY', default='')

# Google Cloud Speech-to-Text v1
GOOGLE_SPEECH_API_KEY = config('GOOGLE_SPEECH_API_KEY', default='')

# HOMER SIP capture (heplify-server → PostgreSQL). Source of per-leg SIP for the
# CDR viewer; captures TLS/wss legs in cleartext. See apps/xml_cdr/sip_capture.py.
HOMER_ENABLED = config('HOMER_ENABLED', default=False, cast=bool)
HOMER_DB_HOST = config('HOMER_DB_HOST', default='127.0.0.1')
HOMER_DB_PORT = config('HOMER_DB_PORT', default=5432, cast=int)
HOMER_DB_NAME = config('HOMER_DB_NAME', default='homer_data')
HOMER_DB_USER = config('HOMER_DB_USER', default='homer')
HOMER_DB_PASSWORD = config('HOMER_DB_PASSWORD', default='')
