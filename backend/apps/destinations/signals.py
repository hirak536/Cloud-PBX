import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='destinations.Destination')
def auto_create_fax_box(sender, instance, **kwargs):
    """
    When a DID has fax_receive=True and no fax box linked, auto-create
    a Fax box using the DID number and assign it back to the destination.

    Also self-heals the common breakage where the front end saved the DID
    with fax_receive/dest_type=fax but fax_id=None (the fax box exists on the
    Fax page but the DID->Fax link was never persisted): if a fax box already
    exists for this number in the same domain, relink it instead of leaving the
    DID pointing at nothing (which fails outbound with DESTINATION_OUT_OF_ORDER).
    """
    needs_fax = instance.fax_receive or instance.dest_type == 'fax'
    if not needs_fax or instance.fax_id:
        return

    try:
        from apps.fax.models import Fax

        number = instance.destination_number or ''

        # Self-heal: a fax box for this number may already exist in this domain
        # (created via the DID dialog) but never got linked back. Reuse it rather
        # than creating a duplicate.
        fax = None
        if number:
            fax = Fax.objects.filter(
                domain=instance.domain,
                fax_caller_id_number=number,
            ).first()

        created = False
        if fax is None:
            # Use a unique extension based on the DID number (last 4 digits fallback to full)
            did = number.lstrip('+').lstrip('1')
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
                fax_name=instance.destination_name or number or 'Fax',
                fax_extension=extension,
                fax_caller_id_number=number,
                fax_caller_id_name=instance.destination_name or 'Fax',
                fax_enabled=True,
            )
            created = True

        # Assign back without triggering this signal again
        sender.objects.filter(pk=instance.pk).update(fax=fax)
        instance.fax = fax
        instance.fax_id = fax.pk

        # Keep the direct-fax action target pointed at the fax box so the
        # dialplan routes correctly (empty target => DESTINATION_OUT_OF_ORDER).
        instance.actions.filter(dest_type='fax').exclude(
            dest_target_uuid=fax.pk
        ).update(dest_target_uuid=fax.pk)

        logger.info(
            f'auto_create_fax_box: {"created" if created else "relinked"} Fax '
            f'{fax.fax_uuid} ext={fax.fax_extension} for DID {number}'
        )

    except Exception as exc:
        logger.error(f'auto_create_fax_box: failed for DID {instance.destination_number}: {exc}')
