from core.permissions import HasPBXPermission


class MusicOnHoldPermission(HasPBXPermission):
    """Permission gate for the Music On Hold resource.

    Maps HTTP verbs to FusionPBX permission names stored in v_group_permissions.
    Superusers bypass all checks.
    """

    action_permissions = {
        'list': 'music_on_hold_view',
        'retrieve': 'music_on_hold_view',
        'create': 'music_on_hold_add',
        'update': 'music_on_hold_edit',
        'partial_update': 'music_on_hold_edit',
        'destroy': 'music_on_hold_delete',
    }
