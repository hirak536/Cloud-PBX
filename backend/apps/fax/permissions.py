from core.permissions import HasPBXPermission


class FaxPermission(HasPBXPermission):
    """Permission gate for the Fax resource."""

    action_permissions = {
        'list': 'fax_view',
        'retrieve': 'fax_view',
        'create': 'fax_add',
        'update': 'fax_edit',
        'partial_update': 'fax_edit',
        'destroy': 'fax_delete',
    }


class FaxQueuePermission(HasPBXPermission):
    """Permission gate for the FaxQueue resource."""

    action_permissions = {
        'list': 'fax_queue_view',
        'retrieve': 'fax_queue_view',
        'create': 'fax_queue_add',
        'update': 'fax_queue_edit',
        'partial_update': 'fax_queue_edit',
        'destroy': 'fax_queue_delete',
    }
