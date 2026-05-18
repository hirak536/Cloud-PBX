from core.permissions import HasPBXPermission


class ExtensionPermission(HasPBXPermission):
    """Permission gate for the Extension resource.

    Maps HTTP verbs to FusionPBX permission names stored in v_group_permissions.
    Superusers bypass all checks.
    """

    action_permissions = {
        'list': 'extension_view',
        'retrieve': 'extension_view',
        'create': 'extension_add',
        'update': 'extension_edit',
        'partial_update': 'extension_edit',
        'destroy': 'extension_delete',
        'reload': 'extension_edit',
        'bulk_import': 'extension_add',
        'export': 'extension_view',
    }
