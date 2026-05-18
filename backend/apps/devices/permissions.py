from core.permissions import HasPBXPermission


class DevicePermission(HasPBXPermission):
    """Permission gate for the Device resource."""

    action_permissions = {
        'list': 'device_view',
        'retrieve': 'device_view',
        'create': 'device_add',
        'update': 'device_edit',
        'partial_update': 'device_edit',
        'destroy': 'device_delete',
        'provision': 'device_edit',
    }


class DeviceSettingPermission(HasPBXPermission):
    """Permission gate for the DeviceSetting resource."""

    action_permissions = {
        'list': 'device_view',
        'retrieve': 'device_view',
        'create': 'device_add',
        'update': 'device_edit',
        'partial_update': 'device_edit',
        'destroy': 'device_delete',
    }


class DeviceLinePermission(HasPBXPermission):
    """Permission gate for the DeviceLine resource."""

    action_permissions = {
        'list': 'device_view',
        'retrieve': 'device_view',
        'create': 'device_add',
        'update': 'device_edit',
        'partial_update': 'device_edit',
        'destroy': 'device_delete',
    }


class DeviceProfilePermission(HasPBXPermission):
    """Permission gate for the DeviceProfile resource."""

    action_permissions = {
        'list': 'device_view',
        'retrieve': 'device_view',
        'create': 'device_add',
        'update': 'device_edit',
        'partial_update': 'device_edit',
        'destroy': 'device_delete',
    }


class DeviceProfileSettingPermission(HasPBXPermission):
    """Permission gate for the DeviceProfileSetting resource."""

    action_permissions = {
        'list': 'device_view',
        'retrieve': 'device_view',
        'create': 'device_add',
        'update': 'device_edit',
        'partial_update': 'device_edit',
        'destroy': 'device_delete',
    }
