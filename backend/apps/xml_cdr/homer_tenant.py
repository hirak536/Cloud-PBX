"""Tenant attribution for HOMER-captured SIP.

HOMER stores every tenant's SIP in one shared homer_data store with no tenant
tag (all tenants share the SIP domain 23.189.208.80, so the SIP messages carry
nothing that identifies a tenant). To filter captured calls per tenant we
attribute each message at query time by matching its numbers against the
Cloud PBX DID (Destination) and Extension tables.

Attribution rules for one captured SIP message (from_user / to_user / ruri_user):
  - Inbound  carrier→PBX: the DID is in to_user / ruri_user.
  - Outbound PBX→carrier: the DID/extension is in from_user.
A message belongs to a tenant if ANY of its numbers resolves to that tenant's
DID or extension. Numbers that resolve to no tenant (scanner floods, unassigned
DIDs) are 'unattributed' and surfaced only to superadmins.

The number→tenant index is built once and cached briefly; DIDs/extensions
change rarely relative to the query rate.
"""
import re

from django.core.cache import cache

_CACHE_KEY = 'homer:number_tenant_index:v1'
_CACHE_TTL = 300  # seconds


def _norm(number):
    """Normalise a phone number to its last 10 digits (US), dropping +1/punctuation.

    DIDs are stored E.164 (+12812715519); SIP from_user/to_user vary (+1..., 1...,
    10-digit, or an internal extension like '101-GMD'). Reducing both sides to the
    last 10 digits makes DID matching robust. Pure extensions (1-5 digits) are
    handled separately by the extension index, not here.
    """
    if not number:
        return ''
    digits = re.sub(r'\D', '', number)
    if len(digits) == 11 and digits.startswith('1'):
        digits = digits[1:]
    return digits[-10:] if len(digits) >= 10 else digits


def build_index():
    """Build {number_or_ext: tenant_uuid_str} for all enabled DIDs and extensions.

    Keys:
      - 10-digit DID  → tenant (from Destination)
      - extension number (e.g. '101') → tenant (from Extension)
      - sip_username (e.g. '101-GMD') → tenant (from Extension)
    Cached; call invalidate_index() after DID/extension changes if freshness matters.
    """
    cached = cache.get(_CACHE_KEY)
    if cached is not None:
        return cached

    from apps.destinations.models import Destination
    from apps.extensions.models import Extension

    idx = {}
    for did, tid in Destination.objects.filter(
        destination_enabled=True, tenant__isnull=False
    ).values_list('destination_number', 'tenant_id'):
        n = _norm(did)
        if n:
            idx[n] = str(tid)

    for ext, sip_u, tid in Extension.objects.filter(
        enabled=True, tenant__isnull=False
    ).values_list('extension', 'sip_username', 'tenant_id'):
        if ext:
            idx[str(ext)] = str(tid)
        if sip_u:
            idx[str(sip_u)] = str(tid)

    cache.set(_CACHE_KEY, idx, _CACHE_TTL)
    return idx


def invalidate_index():
    cache.delete(_CACHE_KEY)


def attribute(numbers, index=None):
    """Return the tenant_uuid (str) for the first of `numbers` that resolves, else None.

    `numbers` is an iterable of raw SIP user values (from_user, to_user, ruri_user).
    Tries an exact match first (extensions / sip_usernames), then the normalised
    10-digit form (DIDs).
    """
    idx = index if index is not None else build_index()
    for raw in numbers:
        if not raw:
            continue
        if raw in idx:                       # exact: extension or sip_username
            return idx[raw]
        n = _norm(raw)
        if n and n in idx:                   # normalised: DID
            return idx[n]
    return None
