from core.permissions import HasPBXPermission


class RingGroupPermission(HasPBXPermission):
    """Permission gate for the Ring Group resource.

    Maps ViewSet actions to FusionPBX-style permission names. Superusers and
    staff admins bypass; standard users are gated by group permissions or their
    per-user allowed_actions grants.
    """

    action_permissions = {
        'list': 'ring_group_view',
        'retrieve': 'ring_group_view',
        'create': 'ring_group_add',
        'update': 'ring_group_edit',
        'partial_update': 'ring_group_edit',
        'destroy': 'ring_group_delete',
    }
