"""
Cache invalidation signals for FreeSWITCH XML (dialplan, directory, configuration).

Fires post_save/post_delete for every model whose data is read by the XML
generators, deleting the relevant cached responses for the affected domain.

Called from FreeswitchConfigConfig.ready() in apps.py.
"""
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)


# ── Low-level cache helpers ───────────────────────────────────────────────────

def _delete(key):
    try:
        cache.delete(key)
    except Exception as exc:
        logger.warning('Cache delete failed key=%s: %s', key, exc)


def _delete_pattern(pattern):
    try:
        cache.delete_pattern(pattern)
    except Exception as exc:
        logger.warning('Cache delete_pattern failed pattern=%s: %s', pattern, exc)


# ── Per-section invalidation helpers ─────────────────────────────────────────

def _invalidate_dialplan(domain_name):
    if domain_name:
        _delete(f'dialplan:xml:{domain_name}')
        logger.debug('Dialplan cache invalidated domain=%s', domain_name)


def _invalidate_dialplan_all():
    _delete_pattern('dialplan:xml:*')
    logger.debug('Dialplan cache invalidated all domains')


def _invalidate_directory(domain_name):
    """Invalidate full-domain directory + all per-user keys for that domain."""
    if domain_name:
        _delete(f'directory:xml:{domain_name}')
        _delete_pattern(f'directory:xml:{domain_name}:*')
        logger.debug('Directory cache invalidated domain=%s', domain_name)


def _invalidate_directory_all():
    _delete_pattern('directory:xml:*')
    logger.debug('Directory cache invalidated all domains')


def _invalidate_config(config_name, domain_name):
    if config_name and domain_name:
        _delete(f'config:xml:{config_name}:{domain_name}')
        logger.debug('Config cache invalidated config=%s domain=%s', config_name, domain_name)


def _invalidate_config_all(config_name):
    _delete_pattern(f'config:xml:{config_name}:*')
    logger.debug('Config cache invalidated config=%s all domains', config_name)


# ── Domain name resolution ────────────────────────────────────────────────────

def _domain_name(instance):
    domain = getattr(instance, 'domain', None)
    if domain is None:
        return None
    return getattr(domain, 'domain_name', None)


# ── Signal handlers ───────────────────────────────────────────────────────────

def _reset_sticky_did_cache():
    """Reset the in-process sticky DID set so it is rebuilt on the next request."""
    from freeswitch_config import views as _fs_views
    _fs_views._sticky_did_cache = set()
    _fs_views._sticky_did_cache_built = False


def _on_dialplan_model(sender, instance, **kwargs):
    """Invalidate all dialplan cache — pattern delete catches any domain key variant."""
    _invalidate_dialplan_all()
    if sender.__name__ in ('CustomDestination',):
        _reset_sticky_did_cache()


def _on_dialplan_nullable(sender, instance, **kwargs):
    """Invalidate all dialplan cache — shared/nullable domain models affect all tenants."""
    _invalidate_dialplan_all()
    if sender.__name__ in ('Destination',):
        _reset_sticky_did_cache()


def _on_directory_model(sender, instance, **kwargs):
    """Invalidate all directory cache."""
    _invalidate_directory_all()


def _on_ivr_model(sender, instance, **kwargs):
    """IvrMenu change: invalidate dialplan + ivr.conf."""
    _invalidate_dialplan_all()
    _invalidate_config_all('ivr.conf')


def _on_conference_model(sender, instance, **kwargs):
    """ConferenceProfile change: invalidate dialplan + conference.conf."""
    _invalidate_dialplan_all()
    _invalidate_config_all('conference.conf')


def _on_voicemail_model(sender, instance, **kwargs):
    """Voicemail change: invalidate dialplan + directory + voicemail.conf."""
    _invalidate_dialplan_all()
    _invalidate_directory_all()
    _invalidate_config_all('voicemail.conf')


def _on_extension_model(sender, instance, **kwargs):
    """Extension change: invalidate dialplan + directory (SIP credentials live here)."""
    _invalidate_dialplan_all()
    _invalidate_directory_all()


# ── Signal registration ───────────────────────────────────────────────────────

def register_signals():
    """
    Register all cache invalidation signals.
    Called from FreeswitchConfigConfig.ready().
    dispatch_uid prevents double-registration if ready() fires more than once.
    """
    from django.db.models.signals import post_save, post_delete

    from apps.extensions.models import Extension
    from apps.destinations.models import Destination
    from apps.dialplans.models import Dialplan
    from apps.outbound_routes.models import OutboundRoute
    from apps.ivr_menus.models import IvrMenu
    from apps.ring_groups.models import RingGroup
    from apps.time_conditions.models import TimeCondition
    from apps.working_hours.models import WorkingHours
    from apps.call_flows.models import CallFlow
    from apps.conferences.models import ConferenceProfile
    from apps.custom_destinations.models import CustomDestination
    from apps.call_parking.models import CallParkingSlot
    from apps.voicemails.models import Voicemail
    from apps.fax.models import Fax
    from apps.gateways.models import Gateway

    def _connect(handler, model):
        name = model.__name__
        post_save.connect(handler, sender=model, dispatch_uid=f'fscache_{name}_save')
        post_delete.connect(handler, sender=model, dispatch_uid=f'fscache_{name}_delete')

    # Extension: dialplan + directory
    _connect(_on_extension_model, Extension)

    # Voicemail: dialplan + directory + voicemail.conf
    _connect(_on_voicemail_model, Voicemail)

    # IvrMenu: dialplan + ivr.conf
    _connect(_on_ivr_model, IvrMenu)

    # ConferenceProfile: dialplan + conference.conf
    _connect(_on_conference_model, ConferenceProfile)

    # Dialplan-only models — invalidates specific domain or all if domain is null
    for model in [Dialplan, RingGroup, TimeCondition,
                  WorkingHours, CallFlow, CustomDestination, CallParkingSlot, Fax]:
        _connect(_on_dialplan_model, model)

    # Shared/nullable-domain models — always invalidates all domains
    for model in [Destination, OutboundRoute, Gateway]:
        _connect(_on_dialplan_nullable, model)
