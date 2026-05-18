"""
Celery tasks for call_centers app.
Handles asynchronous FreeSWITCH ESL operations for call center management.
"""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def reload_call_center(self, queue_name: str) -> dict:
    """
    Reload a call center queue configuration via ESL.
    Invokes: callcenter_config queue load <queue_name>
    """
    try:
        from esl.client import get_esl_client
        esl = get_esl_client()
        result = esl.api(f'callcenter_config queue load {queue_name}')
        logger.info('Call center queue %s reloaded. ESL response: %s', queue_name, result)
        return {'queue': queue_name, 'result': result, 'status': 'ok'}
    except Exception as exc:
        logger.error('Failed to reload call center queue %s: %s', queue_name, exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def set_agent_status(self, agent_name: str, new_status: str) -> dict:
    """
    Set an agent's status via ESL.
    Valid statuses: Available, Available (On Demand), On Break, Logged Out.
    Invokes: callcenter_config agent set status <agent_name> <status>
    """
    try:
        from esl.client import get_esl_client
        esl = get_esl_client()
        result = esl.api(f'callcenter_config agent set status {agent_name} {new_status}')
        logger.info('Agent %s status set to %s. ESL: %s', agent_name, new_status, result)
        return {'agent': agent_name, 'status': new_status, 'result': result}
    except Exception as exc:
        logger.error('Failed to set agent %s status: %s', agent_name, exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def reload_all_call_centers(self) -> dict:
    """
    Reload all call center queues by reloading FreeSWITCH XML config.
    """
    try:
        from esl.client import get_esl_client
        esl = get_esl_client()
        xml_result = esl.reload_xml()
        logger.info('XML reloaded for call centers: %s', xml_result)
        return {'xml_reload': xml_result, 'status': 'ok'}
    except Exception as exc:
        logger.error('Failed to reload all call centers: %s', exc)
        raise self.retry(exc=exc)
