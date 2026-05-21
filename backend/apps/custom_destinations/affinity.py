"""
Caller-extension affinity helpers.

Tenant-wide: a customer's sticky extension applies across every DID for that
tenant. Live updates come from outbound XmlCdr post-save; the one-time manual
seed populates known relationships. Inbound CDRs are not used (the answering
extension in legacy data is often an IVR target rather than a real human).
"""
import re
import logging

from .models import CallerExtensionAffinity

log = logging.getLogger(__name__)


def normalize_number(num):
    """Strip non-digits, drop leading US country code, keep last 10."""
    if not num:
        return ''
    digits = re.sub(r'\D', '', str(num))
    if len(digits) > 10 and digits.startswith('1'):
        digits = digits[1:]
    return digits[-10:] if len(digits) >= 10 else digits


def upsert_affinity(tenant, customer, extension, when, *, domain=None, source='outbound'):
    """
    Upsert (tenant, customer) → extension. Only overwrites if `when` is newer
    than the stored last_seen — safe for out-of-order signal delivery and
    idempotent for repeated seed runs.
    """
    cust_n = normalize_number(customer)
    if not cust_n or not extension or not when:
        return None

    obj, created = CallerExtensionAffinity.objects.get_or_create(
        tenant=tenant,
        caller_number=cust_n,
        defaults={
            'domain': domain,
            'extension_number': extension,
            'last_seen': when,
            'source': source,
        },
    )
    if created:
        return obj
    if when > obj.last_seen:
        obj.extension_number = extension
        obj.last_seen = when
        obj.source = source
        if domain and not obj.domain_id:
            obj.domain = domain
        obj.save(update_fields=['extension_number', 'last_seen', 'source', 'domain'])
    return obj
