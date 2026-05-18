"""Celery tasks for the dialplans app."""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def reload_dialplan(self, dialplan_uuid: str):
    """Trigger a FreeSWITCH XML reload after a dialplan change.

    Dispatches ``reloadxml`` via ESL; retries on ESL connectivity failures.
    """
    try:
        from esl.tasks import reload_xml  # noqa: PLC0415
        reload_xml.delay()
        logger.info('reload_dialplan: triggered reloadxml for dialplan %s', dialplan_uuid)
    except Exception as exc:
        logger.warning(
            'reload_dialplan: ESL task failed for %s: %s – retrying',
            dialplan_uuid,
            exc,
        )
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def reload_all_dialplans(self, domain_uuid: str = None):
    """Reload all dialplans (domain-wide or global).

    Called after bulk operations or context-level changes.
    """
    try:
        from esl.tasks import reload_xml  # noqa: PLC0415
        reload_xml.delay()
        label = domain_uuid or 'global'
        logger.info('reload_all_dialplans: triggered reloadxml for %s', label)
    except Exception as exc:
        logger.warning('reload_all_dialplans: ESL task failed: %s – retrying', exc)
        raise self.retry(exc=exc)
