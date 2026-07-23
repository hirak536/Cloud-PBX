from core.permissions import HasPBXPermission


class ConferencePermission(HasPBXPermission):
    """
    Permission class for Conferences.
    Maps to FusionPBX conferences permission group.
    """
    view_permission = 'conferences_view'
    add_permission = 'conferences_add'
    edit_permission = 'conferences_edit'
    delete_permission = 'conferences_delete'

    action_permissions = {
        'list': 'conferences_view',
        'retrieve': 'conferences_view',
        'create': 'conferences_add',
        'update': 'conferences_edit',
        'partial_update': 'conferences_edit',
        'destroy': 'conferences_delete',
    }


class ConferenceProfilePermission(HasPBXPermission):
    """Permission class for Conference Profiles."""
    view_permission = 'conference_profiles_view'
    add_permission = 'conference_profiles_add'
    edit_permission = 'conference_profiles_edit'
    delete_permission = 'conference_profiles_delete'


class ConferenceCenterPermission(HasPBXPermission):
    """Permission class for Conference Centers."""
    view_permission = 'conference_centers_view'
    add_permission = 'conference_centers_add'
    edit_permission = 'conference_centers_edit'
    delete_permission = 'conference_centers_delete'


class ConferenceControlPermission(HasPBXPermission):
    """Permission class for Conference Controls."""
    view_permission = 'conference_controls_view'
    add_permission = 'conference_controls_add'
    edit_permission = 'conference_controls_edit'
    delete_permission = 'conference_controls_delete'
