import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='destinations.Destination')
def auto_create_fax_box(sender, instance, **kwargs):
    """
    When a DID has fax_receive=True and no fax box linked, auto-create
    a Fax box using the DID number and assign it back to the destination.
    """
    if not instance.fax_receive or instance.fax_id:
        return

    try:
        from apps.fax.models import Fax

        # Use a unique extension based on the DID number (last 4 digits fallback to full)
        did = instance.destination_number.lstrip('+').lstrip('1') if instance.destination_number else ''
        extension = did[-4:] if len(did) >= 4 else did or '9000'

        # Ensure extension is unique within the domain
        base_ext = extension
        counter = 1
        while Fax.objects.filter(domain=instance.domain, fax_extension=extension).exists():
            extension = f'{base_ext}{counter}'
            counter += 1

        fax = Fax.objects.create(
            tenant=instance.tenant,
            domain=instance.domain,
            fax_name=instance.destination_name or instance.destination_number or 'Fax',
            fax_extension=extension,
            fax_caller_id_number=instance.destination_number or '',
            fax_caller_id_name=instance.destination_name or 'Fax',
            fax_enabled=True,
        )

        # Assign back without triggering this signal again
        sender.objects.filter(pk=instance.pk).update(fax=fax)
        instance.fax = fax
        instance.fax_id = fax.pk

        logger.info(
            f'auto_create_fax_box: created Fax {fax.fax_uuid} ext={extension} '
            f'for DID {instance.destination_number}'
        )

    except Exception as exc:
        logger.error(f'auto_create_fax_box: failed for DID {instance.destination_number}: {exc}')
