"""
Celery tasks for sip_profiles app.
Handles asynchronous FreeSWITCH ESL operations for SIP profile management.
"""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def reload_sip_profile(self, profile_name: str) -> dict:
    """
    Reload (restart) a SIP profile via FreeSWITCH ESL.
    Invokes: sofia profile <name> restart
    """
    try:
        from esl.client import get_esl_client
        esl = get_esl_client()
        result = esl.api(f'sofia profile {profile_name} restart')
        logger.info('SIP profile %s reloaded. ESL response: %s', profile_name, result)
        return {'profile': profile_name, 'result': result, 'status': 'ok'}
    except Exception as exc:
        logger.error('Failed to reload SIP profile %s: %s', profile_name, exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def reload_xml_and_sip_profiles(self) -> dict:
    """
    Reload FreeSWITCH XML config and rescan all SIP profiles.
    Useful after bulk changes to profiles or their settings.
    """
    try:
        from esl.client import get_esl_client
        esl = get_esl_client()
        xml_result = esl.reload_xml()
        rescan_result = esl.api('sofia profile internal rescan')
        logger.info('XML reloaded: %s. Sofia rescan: %s', xml_result, rescan_result)
        return {
            'xml_reload': xml_result,
            'sofia_rescan': rescan_result,
            'status': 'ok',
        }
    except Exception as exc:
        logger.error('Failed to reload XML/SIP profiles: %s', exc)
        raise self.retry(exc=exc)
