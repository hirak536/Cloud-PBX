import os
from celery import Celery
from celery.signals import setup_logging

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')

app = Celery('cloudpbx')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


@setup_logging.connect
def configure_logging(**kwargs):
    """Use Django's LOGGING config inside Celery workers.

    By default Celery hijacks the root logger and routes task logs to its own
    --logfile, which bypasses the per-logger handlers in Django's LOGGING dict
    (e.g. apps.fax / apps.voicemails -> /var/log/cloudpbx/app.log). Wiring this
    signal makes worker logging identical to the web process, so task DEBUG/INFO
    lines land in app.log as configured.
    """
    from logging.config import dictConfig
    from django.conf import settings
    dictConfig(settings.LOGGING)

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
