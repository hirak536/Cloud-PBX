from core.permissions import HasPBXPermission


class VoicemailPermission(HasPBXPermission):
    """Permission gate for the Voicemail resource."""

    action_permissions = {
        'list': 'voicemail_view',
        'retrieve': 'voicemail_view',
        'create': 'voicemail_add',
        'update': 'voicemail_edit',
        'partial_update': 'voicemail_edit',
        'destroy': 'voicemail_delete',
        # Message actions
        'messages': 'voicemail_view',
        'download_message': 'voicemail_view',
        'delete_message': 'voicemail_edit',
        'mark_message': 'voicemail_edit',
        # Options / destinations
        'options': 'voicemail_view',
        'destinations': 'voicemail_view',
    }


class VoicemailMessagePermission(HasPBXPermission):
    """Permission gate for VoicemailMessage resource."""

    action_permissions = {
        'list': 'voicemail_view',
        'retrieve': 'voicemail_view',
        'create': 'voicemail_edit',
        'update': 'voicemail_edit',
        'partial_update': 'voicemail_edit',
        'destroy': 'voicemail_delete',
        'download': 'voicemail_view',
    }
