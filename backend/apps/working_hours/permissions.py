from core.permissions import HasPBXPermission


class WorkingHoursPermission(HasPBXPermission):
    action_permissions = {
        'list':           'working_hours_view',
        'retrieve':       'working_hours_view',
        'create':         'working_hours_add',
        'update':         'working_hours_edit',
        'partial_update': 'working_hours_edit',
        'destroy':        'working_hours_delete',
    }
