from core.permissions import HasPBXPermission


class CallCenterPermission(HasPBXPermission):
    """
    Permission class for Call Center Queues.
    Maps to FusionPBX call_center permission group.
    """
    view_permission = 'call_center_view'
    add_permission = 'call_center_add'
    edit_permission = 'call_center_edit'
    delete_permission = 'call_center_delete'


class CallCenterAgentPermission(HasPBXPermission):
    """Permission class for Call Center Agents."""
    view_permission = 'call_center_agent_view'
    add_permission = 'call_center_agent_add'
    edit_permission = 'call_center_agent_edit'
    delete_permission = 'call_center_agent_delete'


class CallCenterTierPermission(HasPBXPermission):
    """Permission class for Call Center Tiers."""
    view_permission = 'call_center_tier_view'
    add_permission = 'call_center_tier_add'
    edit_permission = 'call_center_tier_edit'
    delete_permission = 'call_center_tier_delete'
