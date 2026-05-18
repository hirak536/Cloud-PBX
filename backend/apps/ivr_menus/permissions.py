from core.permissions import HasPBXPermission


class IvrMenuPermission(HasPBXPermission):
    """Permission gate for the IvrMenu resource.

    Maps HTTP verbs to FusionPBX permission names stored in v_group_permissions.
    Superusers bypass all checks.
    """

    action_permissions = {
        'list': 'ivr_menu_view',
        'retrieve': 'ivr_menu_view',
        'create': 'ivr_menu_add',
        'update': 'ivr_menu_edit',
        'partial_update': 'ivr_menu_edit',
        'destroy': 'ivr_menu_delete',
        'reload': 'ivr_menu_edit',
    }


class IvrMenuOptionPermission(HasPBXPermission):
    """Permission gate for the IvrMenuOption resource."""

    action_permissions = {
        'list': 'ivr_menu_view',
        'retrieve': 'ivr_menu_view',
        'create': 'ivr_menu_edit',
        'update': 'ivr_menu_edit',
        'partial_update': 'ivr_menu_edit',
        'destroy': 'ivr_menu_edit',
    }
