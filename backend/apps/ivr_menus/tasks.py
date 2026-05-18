"""Celery tasks for the ivr_menus app."""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def reload_ivr_menu(self, ivr_menu_uuid: str):
    """Trigger a FreeSWITCH XML reload after an IVR menu change.

    Delegates to ``esl.tasks.reload_xml`` which issues ``reloadxml`` over ESL.
    Retries up to 3 times with a 10-second backoff on ESL connection failures.
    """
    try:
        from esl.tasks import reload_xml  # noqa: PLC0415 – late import required
        reload_xml.delay()
        logger.info('reload_ivr_menu: triggered reloadxml for ivr_menu %s', ivr_menu_uuid)
    except Exception as exc:
        logger.warning(
            'reload_ivr_menu: ESL task failed for %s: %s – retrying',
            ivr_menu_uuid,
            exc,
        )
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def reload_ivr_menus_for_domain(self, domain_uuid: str):
    """Reload XML for all IVR menus in a given domain."""
    try:
        from esl.tasks import reload_xml  # noqa: PLC0415
        reload_xml.delay()
        logger.info(
            'reload_ivr_menus_for_domain: triggered reloadxml for domain %s',
            domain_uuid,
        )
    except Exception as exc:
        logger.warning(
            'reload_ivr_menus_for_domain: ESL task failed for domain %s: %s – retrying',
            domain_uuid,
            exc,
        )
        raise self.retry(exc=exc)
