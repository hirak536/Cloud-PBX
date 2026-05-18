from core.permissions import HasPBXPermission


class DialplanPermission(HasPBXPermission):
    """Permission gate for the Dialplan resource."""

    action_permissions = {
        'list': 'dialplan_view',
        'retrieve': 'dialplan_view',
        'create': 'dialplan_add',
        'update': 'dialplan_edit',
        'partial_update': 'dialplan_edit',
        'destroy': 'dialplan_delete',
        'reload': 'dialplan_edit',
        'xml': 'dialplan_view',
        'inbound': 'dialplan_view',
        'outbound': 'dialplan_view',
    }
