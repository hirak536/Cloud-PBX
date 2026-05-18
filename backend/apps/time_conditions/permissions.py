from core.permissions import HasPBXPermission


class TimeConditionPermission(HasPBXPermission):
    """Permission gate for the TimeCondition resource.

    Maps HTTP verbs to FusionPBX permission names stored in v_group_permissions.
    Superusers bypass all checks.
    """

    action_permissions = {
        'list': 'time_condition_view',
        'retrieve': 'time_condition_view',
        'create': 'time_condition_add',
        'update': 'time_condition_edit',
        'partial_update': 'time_condition_edit',
        'destroy': 'time_condition_delete',
        'reload': 'time_condition_edit',
    }


class TimeConditionSettingPermission(HasPBXPermission):
    """Permission gate for the TimeConditionSetting resource."""

    action_permissions = {
        'list': 'time_condition_view',
        'retrieve': 'time_condition_view',
        'create': 'time_condition_edit',
        'update': 'time_condition_edit',
        'partial_update': 'time_condition_edit',
        'destroy': 'time_condition_edit',
    }
