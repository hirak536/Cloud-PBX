"""Celery tasks for the call_flows app."""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def reload_call_flow(self, call_flow_uuid: str):
    """Trigger a FreeSWITCH XML reload after a call flow change.

    Delegates to ``esl.tasks.reload_xml`` which issues ``reloadxml`` over ESL.
    Retries up to 3 times with a 10-second backoff on ESL connection failures.
    """
    try:
        from esl.tasks import reload_xml  # noqa: PLC0415 – late import required
        reload_xml.delay()
        logger.info('reload_call_flow: triggered reloadxml for call_flow %s', call_flow_uuid)
    except Exception as exc:
        logger.warning(
            'reload_call_flow: ESL task failed for %s: %s – retrying',
            call_flow_uuid,
            exc,
        )
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def toggle_call_flow(self, call_flow_uuid: str, new_status: str):
    """Toggle call flow status and trigger FreeSWITCH XML reload.

    Parameters
    ----------
    call_flow_uuid:
        UUID of the CallFlow to toggle.
    new_status:
        New status value ('true' or 'false').
    """
    try:
        from apps.call_flows.models import CallFlow  # noqa: PLC0415
        CallFlow.objects.filter(call_flow_uuid=call_flow_uuid).update(
            call_flow_status=new_status
        )
        from esl.tasks import reload_xml  # noqa: PLC0415
        reload_xml.delay()
        logger.info(
            'toggle_call_flow: set call_flow %s to %s and triggered reloadxml',
            call_flow_uuid,
            new_status,
        )
    except Exception as exc:
        logger.warning(
            'toggle_call_flow: failed for %s: %s – retrying',
            call_flow_uuid,
            exc,
        )
        raise self.retry(exc=exc)
