"""
Celery tasks for conferences app.
Handles asynchronous FreeSWITCH ESL operations for conference management.
"""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def kick_conference_member(self, conference_name: str, member_id: str) -> dict:
    """
    Kick a participant from a conference by member ID via ESL.
    Invokes: conference <name> kick <member_id>
    """
    try:
        from esl.client import get_esl_client
        esl = get_esl_client()
        result = esl.conference_cmd(conference_name, f'kick {member_id}')
        logger.info(
            'Kicked member %s from conference %s. ESL: %s',
            member_id, conference_name, result,
        )
        return {'conference': conference_name, 'member_id': member_id, 'result': result, 'status': 'ok'}
    except Exception as exc:
        logger.error('Failed to kick member %s from conference %s: %s', member_id, conference_name, exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def mute_conference_member(self, conference_name: str, member_id: str) -> dict:
    """
    Mute a participant in a conference by member ID via ESL.
    Invokes: conference <name> mute <member_id>
    """
    try:
        from esl.client import get_esl_client
        esl = get_esl_client()
        result = esl.conference_cmd(conference_name, f'mute {member_id}')
        logger.info(
            'Muted member %s in conference %s. ESL: %s',
            member_id, conference_name, result,
        )
        return {'conference': conference_name, 'member_id': member_id, 'result': result, 'status': 'ok'}
    except Exception as exc:
        logger.error('Failed to mute member %s in conference %s: %s', member_id, conference_name, exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def record_conference(self, conference_name: str, record_path: str) -> dict:
    """
    Start recording a conference via ESL.
    Invokes: conference <name> record <path>
    """
    try:
        from esl.client import get_esl_client
        esl = get_esl_client()
        result = esl.conference_cmd(conference_name, f'record {record_path}')
        logger.info('Started recording conference %s to %s. ESL: %s', conference_name, record_path, result)
        return {'conference': conference_name, 'record_path': record_path, 'result': result, 'status': 'ok'}
    except Exception as exc:
        logger.error('Failed to record conference %s: %s', conference_name, exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def reload_conference_xml(self) -> dict:
    """
    Reload FreeSWITCH XML config to apply conference configuration changes.
    """
    try:
        from esl.client import get_esl_client
        esl = get_esl_client()
        result = esl.reload_xml()
        logger.info('XML reloaded for conferences: %s', result)
        return {'xml_reload': result, 'status': 'ok'}
    except Exception as exc:
        logger.error('Failed to reload XML for conferences: %s', exc)
        raise self.retry(exc=exc)
