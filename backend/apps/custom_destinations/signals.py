"""
Live affinity updates from outbound XmlCdr rows.

Rule: when an outbound call is recorded with a resolved extension, upsert
(tenant, did=caller_id_number, customer=destination_number) → extension.
Inbound CDRs are ignored (the answering extension is often an IVR target
rather than a real human).
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.xml_cdr.models import XmlCdr
from .affinity import upsert_affinity

log = logging.getLogger(__name__)


@receiver(post_save, sender=XmlCdr, dispatch_uid='affinity_xmlcdr_post_save')
def update_affinity_from_outbound_cdr(sender, instance, created, **kwargs):
    if not created:
        return
    if instance.direction != 'outbound':
        return
    if not instance.extension_number:
        return
    if not instance.tenant_id:
        return
    try:
        upsert_affinity(
            tenant=instance.tenant,
            customer=instance.destination_number,
            extension=instance.extension_number,
            when=instance.start_stamp or instance.insert_date,
            domain=instance.domain,
            source='outbound',
        )
    except Exception as exc:
        log.exception('affinity upsert failed for XmlCdr %s: %s', instance.pk, exc)
