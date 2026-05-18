"""
Utility to detect cross-model extension number conflicts within a tenant.

Checks that a given number (as string or int) is not already used by:
  - Extension.extension
  - RingGroup.ring_group_extension
  - IvrMenu.ivr_menu_extension
  - CallParkingSlot.slot_number
"""


def check_extension_conflict(number, tenant, exclude_model=None, exclude_pk=None):
    """
    Returns a list of conflict description strings, empty if no conflicts.

    :param number: The number to check (str or int).
    :param tenant: The Tenant instance.
    :param exclude_model: Model class to skip (the caller's own model).
    :param exclude_pk: PK of the current instance to exclude (for updates).
    """
    import logging
    from apps.extensions.models import Extension
    from apps.ring_groups.models import RingGroup
    from apps.ivr_menus.models import IvrMenu
    from apps.call_parking.models import CallParkingSlot

    _log = logging.getLogger(__name__)

    if not tenant:
        return []

    conflicts = []
    num_str = str(number)

    if exclude_model is not Extension:
        qs = Extension.objects.filter(tenant=tenant, extension=num_str)
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        if qs.exists():
            conflicts.append(f'{num_str} is already used by an Extension.')

    if exclude_model is not RingGroup:
        qs = RingGroup.objects.filter(tenant=tenant, ring_group_extension=num_str)
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        _log.warning('RingGroup conflict check: tenant=%s (%s), number=%s, matches=%s',
                     getattr(tenant, 'tenant_uuid', tenant),
                     getattr(tenant, 'tenant_code', '?'),
                     num_str,
                     list(qs.values('ring_group_uuid', 'ring_group_extension', 'tenant_id')))
        if qs.exists():
            conflicts.append(f'{num_str} is already used by a Ring Group.')

    if exclude_model is not IvrMenu:
        qs = IvrMenu.objects.filter(tenant=tenant, ivr_menu_extension=num_str)
        if qs.exists():
            conflicts.append(f'{num_str} is already used by an IVR Menu.')

    if exclude_model is not CallParkingSlot:
        try:
            qs = CallParkingSlot.objects.filter(tenant=tenant, slot_number=int(num_str))
            if qs.exists():
                conflicts.append(f'{num_str} is already used by a Call Parking slot.')
        except (ValueError, TypeError):
            pass

    return conflicts
