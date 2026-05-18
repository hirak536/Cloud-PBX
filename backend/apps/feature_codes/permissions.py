from core.permissions import HasPBXPermission


class FeatureCodePermission(HasPBXPermission):
    """Permission gate for the FeatureCode resource.

    Maps HTTP verbs to FusionPBX permission names stored in v_group_permissions.
    Superusers bypass all checks.
    """

    action_permissions = {
        'list': 'feature_code_view',
        'retrieve': 'feature_code_view',
        'create': 'feature_code_add',
        'update': 'feature_code_edit',
        'partial_update': 'feature_code_edit',
        'destroy': 'feature_code_delete',
    }
