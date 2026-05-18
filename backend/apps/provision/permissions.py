from core.permissions import HasPBXPermission


class ProvisionTemplatePermission(HasPBXPermission):
    """Permission gate for the ProvisionTemplate resource."""

    action_permissions = {
        'list': 'provision_template_view',
        'retrieve': 'provision_template_view',
        'create': 'provision_template_add',
        'update': 'provision_template_edit',
        'partial_update': 'provision_template_edit',
        'destroy': 'provision_template_delete',
        'preview': 'provision_template_view',
    }
