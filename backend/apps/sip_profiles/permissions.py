from core.permissions import HasPBXPermission


class SipProfilePermission(HasPBXPermission):
    """
    Permission class for SIP profiles.
    Maps to FusionPBX sip_profiles permission group.
    Superusers bypass all checks (handled in base class).
    """
    view_permission = 'sip_profiles_view'
    add_permission = 'sip_profiles_add'
    edit_permission = 'sip_profiles_edit'
    delete_permission = 'sip_profiles_delete'


class SipProfileSettingPermission(HasPBXPermission):
    view_permission = 'sip_profile_settings_view'
    add_permission = 'sip_profile_settings_add'
    edit_permission = 'sip_profile_settings_edit'
    delete_permission = 'sip_profile_settings_delete'


class SipProfileDomainPermission(HasPBXPermission):
    view_permission = 'sip_profiles_view'
    add_permission = 'sip_profiles_add'
    edit_permission = 'sip_profiles_edit'
    delete_permission = 'sip_profiles_delete'
