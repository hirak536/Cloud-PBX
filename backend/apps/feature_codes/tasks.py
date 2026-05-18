"""Celery tasks for the feature_codes app."""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def reload_feature_code(self, feature_code_uuid: str):
    """Trigger a FreeSWITCH XML reload after a feature code change.

    Delegates to ``esl.tasks.reload_xml`` which issues ``reloadxml`` over ESL.
    Retries up to 3 times with a 10-second backoff on ESL connection failures.
    """
    try:
        from esl.tasks import reload_xml  # noqa: PLC0415 – late import required
        reload_xml.delay()
        logger.info(
            'reload_feature_code: triggered reloadxml for feature_code %s',
            feature_code_uuid,
        )
    except Exception as exc:
        logger.warning(
            'reload_feature_code: ESL task failed for %s: %s – retrying',
            feature_code_uuid,
            exc,
        )
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def reload_feature_codes_for_domain(self, domain_uuid: str):
    """Reload XML for all feature codes in a given domain."""
    try:
        from esl.tasks import reload_xml  # noqa: PLC0415
        reload_xml.delay()
        logger.info(
            'reload_feature_codes_for_domain: triggered reloadxml for domain %s',
            domain_uuid,
        )
    except Exception as exc:
        logger.warning(
            'reload_feature_codes_for_domain: ESL task failed for domain %s: %s – retrying',
            domain_uuid,
            exc,
        )
        raise self.retry(exc=exc)
