"""Celery tasks for the devices app."""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def provision_device(self, device_uuid: str):
    """Trigger provisioning config regeneration for a device.

    This task can be extended to push configs to a TFTP/HTTP server,
    send a SIP NOTIFY to the device, or perform any post-save action
    required after a device configuration change.

    Parameters
    ----------
    device_uuid:
        The UUID (as string) of the device to reprovision.
    """
    try:
        from .models import Device
        device = Device.objects.select_related('domain', 'device_profile').prefetch_related(
            'lines', 'settings'
        ).get(device_uuid=device_uuid)

        logger.info(
            'provision_device: regenerating config for device %s (%s)',
            device_uuid,
            device.device_mac_address,
        )

        # Attempt a SIP NOTIFY check-sync if ESL is available
        try:
            from esl.client import get_esl_client
            esl = get_esl_client()
            mac = device.device_mac_address.replace(':', '').lower()
            result = esl.api(f'sofia profile internal send_message {mac} check-sync')
            logger.info(
                'provision_device: SIP NOTIFY check-sync sent for %s: %s',
                mac, result,
            )
        except Exception as esl_exc:
            logger.warning(
                'provision_device: ESL notify skipped for %s: %s',
                device_uuid, esl_exc,
            )

        return {'device_uuid': device_uuid, 'status': 'ok'}

    except Exception as exc:
        logger.warning(
            'provision_device: failed for %s: %s – retrying',
            device_uuid, exc,
        )
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=15)
def bulk_provision_domain(self, domain_uuid: str):
    """Queue provisioning tasks for all enabled devices in a domain.

    Parameters
    ----------
    domain_uuid:
        The UUID (as string) of the domain whose devices should be reprovisioned.
    """
    try:
        from .models import Device
        device_uuids = list(
            Device.objects.filter(
                domain__domain_uuid=domain_uuid,
                device_enabled=True,
            ).values_list('device_uuid', flat=True)
        )
        for uuid_val in device_uuids:
            provision_device.delay(str(uuid_val))
        logger.info(
            'bulk_provision_domain: queued %d devices for domain %s',
            len(device_uuids), domain_uuid,
        )
        return {'domain_uuid': domain_uuid, 'queued': len(device_uuids)}
    except Exception as exc:
        logger.warning(
            'bulk_provision_domain: failed for domain %s: %s – retrying',
            domain_uuid, exc,
        )
        raise self.retry(exc=exc)
