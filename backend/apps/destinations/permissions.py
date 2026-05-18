from core.permissions import HasPBXPermission


class DestinationPermission(HasPBXPermission):
    """Permission gate for the Destination resource.

    Maps HTTP verbs to FusionPBX permission names stored in v_group_permissions.
    Superusers bypass all checks.
    """

    action_permissions = {
        'list': 'destination_view',
        'retrieve': 'destination_view',
        'create': 'destination_add',
        'update': 'destination_edit',
        'partial_update': 'destination_edit',
        'destroy': 'destination_delete',
        'reload': 'destination_edit',
    }
