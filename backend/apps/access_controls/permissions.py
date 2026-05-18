from core.permissions import HasPBXPermission


class AccessControlPermission(HasPBXPermission):
    """Permission gate for the AccessControl resource.

    Maps HTTP verbs to FusionPBX permission names stored in v_group_permissions.
    Superusers bypass all checks.
    """

    action_permissions = {
        'list': 'access_control_view',
        'retrieve': 'access_control_view',
        'create': 'access_control_add',
        'update': 'access_control_edit',
        'partial_update': 'access_control_edit',
        'destroy': 'access_control_delete',
        'reload': 'access_control_edit',
    }


class AccessControlNodePermission(HasPBXPermission):
    """Permission gate for the AccessControlNode resource."""

    action_permissions = {
        'list': 'access_control_view',
        'retrieve': 'access_control_view',
        'create': 'access_control_edit',
        'update': 'access_control_edit',
        'partial_update': 'access_control_edit',
        'destroy': 'access_control_edit',
    }
