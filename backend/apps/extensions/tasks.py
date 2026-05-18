"""Celery tasks for the extensions app."""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def reload_extension(self, extension_uuid: str):
    """Trigger a FreeSWITCH XML reload after an extension change.

    Delegates to ``esl.tasks.reload_xml`` which issues ``reloadxml`` over ESL.
    Retries up to 3 times with a 10-second backoff on ESL connection failures.
    """
    try:
        from esl.tasks import reload_xml  # noqa: PLC0415 – late import required
        reload_xml.delay()
        logger.info('reload_extension: triggered reloadxml for extension %s', extension_uuid)
    except Exception as exc:
        logger.warning(
            'reload_extension: ESL task failed for %s: %s – retrying',
            extension_uuid,
            exc,
        )
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def bulk_reload_extensions(self, domain_uuid: str):
    """Reload XML after a bulk extension import for a given domain."""
    try:
        from esl.tasks import reload_xml  # noqa: PLC0415
        reload_xml.delay()
        logger.info('bulk_reload_extensions: triggered reloadxml for domain %s', domain_uuid)
    except Exception as exc:
        logger.warning(
            'bulk_reload_extensions: ESL task failed for domain %s: %s – retrying',
            domain_uuid,
            exc,
        )
        raise self.retry(exc=exc)
