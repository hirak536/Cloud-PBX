from core.permissions import HasPBXPermission


class CallFlowPermission(HasPBXPermission):
    """Permission gate for the CallFlow resource.

    Maps HTTP verbs to FusionPBX permission names stored in v_group_permissions.
    Superusers bypass all checks.
    """

    action_permissions = {
        'list': 'call_flow_view',
        'retrieve': 'call_flow_view',
        'create': 'call_flow_add',
        'update': 'call_flow_edit',
        'partial_update': 'call_flow_edit',
        'destroy': 'call_flow_delete',
        'toggle': 'call_flow_edit',
    }
