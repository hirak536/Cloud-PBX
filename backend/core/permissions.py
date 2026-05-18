"""DRF permission classes for IHS PBX RBAC.

Permission model
----------------
* Users belong to zero or more :class:`~core.models.Group` rows via
  :class:`~core.models.UserGroup`.
* Each Group can have zero or more :class:`~core.models.GroupPermission`
  rows that name a permission string (e.g. ``'domain_admin'``,
  ``'dialplan_view'``) and carry a boolean ``permission_assigned`` flag.
* A user is considered to *have* a permission when at least one of their
  groups contains a GroupPermission row for that name with
  ``permission_assigned=True``.

All permission checks short-circuit for superusers (``is_superuser=True``).
"""

import logging

from rest_framework.permissions import BasePermission, SAFE_METHODS

from .models import GroupPermission, UserGroup

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Low-level helper
# ---------------------------------------------------------------------------

def check_permission(user, permission_name: str) -> bool:
    """Return ``True`` if *user* holds the named FusionPBX permission.

    The lookup traverses:
        user  ->  UserGroup  ->  Group  ->  GroupPermission(permission_name)

    A superuser always returns ``True`` without hitting the database.

    Parameters
    ----------
    user:
        A :class:`~core.models.User` instance (may be anonymous).
    permission_name:
        The raw FusionPBX permission string, e.g. ``'domain_admin'``.
    """
    if not user or not user.is_authenticated:
        return False
    if getattr(user, 'is_superuser', False):
        return True

    return GroupPermission.objects.filter(
        group__user_groups__user=user,
        permission_name=permission_name,
        permission_assigned=True,
    ).exists()


def get_user_permissions(user) -> set:
    """Return the full set of permission names held by *user*.

    Returns an empty set for unauthenticated users.
    """
    if not user or not user.is_authenticated:
        return set()
    return set(
        GroupPermission.objects.filter(
            group__user_groups__user=user,
            permission_assigned=True,
        ).values_list('permission_name', flat=True)
    )


def get_user_group_names(user) -> set:
    """Return the set of group names the user belongs to."""
    if not user or not user.is_authenticated:
        return set()
    return set(
        UserGroup.objects.filter(user=user)
        .values_list('group__group_name', flat=True)
    )


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class IsSuperAdmin(BasePermission):
    """Grants access only to users with ``is_superuser=True``.

    This maps to FusionPBX's top-level superadmin role that can manage all
    domains and system-wide settings.
    """

    message = 'Superadmin access required.'

    def has_permission(self, request, view):
        return (
            request.user is not None
            and request.user.is_authenticated
            and getattr(request.user, 'is_superuser', False)
        )


class IsTenantAdmin(BasePermission):
    """Grants access to users that hold the ``tenant_admin`` permission
    within their tenant, or to superusers.
    """

    message = 'Tenant admin access required.'
    PERMISSION_NAME = 'tenant_admin'

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if getattr(user, 'is_superuser', False):
            return True
        return check_permission(user, self.PERMISSION_NAME)


# Backward-compat alias — existing views using IsDomainAdmin keep working.
IsDomainAdmin = IsTenantAdmin


class HasPBXPermission(BasePermission):
    """Generic permission gate driven by a ``required_permission`` attribute
    on the view.

    Usage on a ViewSet or APIView::

        class MyViewSet(ModelViewSet):
            required_permission = 'dialplan_view'
            permission_classes = [IsAuthenticated, HasPBXPermission]

    If the view does not set ``required_permission`` the check is skipped and
    access is granted to any authenticated user (effectively equivalent to
    ``IsAuthenticated``).

    Per-action overrides
    ~~~~~~~~~~~~~~~~~~~~~
    You can also define ``action_permissions`` on the view to map ViewSet
    actions to specific permission names::

        class MyViewSet(ModelViewSet):
            action_permissions = {
                'list':    'dialplan_view',
                'retrieve': 'dialplan_view',
                'create':  'dialplan_edit',
                'update':  'dialplan_edit',
                'partial_update': 'dialplan_edit',
                'destroy': 'dialplan_delete',
            }
            permission_classes = [IsAuthenticated, HasPBXPermission]
    """

    message = 'You do not have the required permission.'

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if getattr(user, 'is_superuser', False):
            return True

        # Action-level map takes priority (ViewSet actions).
        action_permissions = getattr(view, 'action_permissions', {})
        action = getattr(view, 'action', None)
        if action and action in action_permissions:
            required = action_permissions[action]
            if required == '':
                return True
            return check_permission(user, required)

        # Fall back to a single required_permission.
        required = getattr(view, 'required_permission', None)
        if required is None:
            return True  # No restriction defined — allow authenticated users.
        if required == '':
            return True
        return check_permission(user, required)

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class IsOwnerOrAdmin(BasePermission):
    """Grants access when the requesting user *owns* the object or is a
    tenant admin / superuser.

    Ownership is determined by comparing ``obj.tenant`` with the user's own
    tenant.  Additionally, if the object has a ``user`` attribute the
    requesting user must match that user (or be an admin).

    Attach after authentication classes::

        permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    """

    message = 'You do not have permission to access this object.'

    def has_permission(self, request, view):
        return request.user is not None and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if getattr(user, 'is_superuser', False):
            return True
        if check_permission(user, 'tenant_admin'):
            return True

        # Tenant ownership check.
        obj_tenant = getattr(obj, 'tenant_id', None)
        user_tenant = getattr(user, 'tenant_id', None)
        if obj_tenant is not None and user_tenant is not None:
            if obj_tenant != user_tenant:
                return False

        # Direct user ownership check (e.g. UserSetting, UserLog).
        obj_user = getattr(obj, 'user_id', None) or getattr(obj, 'user', None)
        if obj_user is not None:
            # Compare primary keys to avoid object identity issues.
            obj_user_pk = obj_user.pk if hasattr(obj_user, 'pk') else obj_user
            return obj_user_pk == user.pk

        return True


class IsSameTenantOrAdmin(BasePermission):
    """Restricts object access to the current request tenant.

    Used on ViewSets where all objects must belong to ``request.tenant``
    unless the caller is a superuser or tenant admin.
    """

    message = 'Cross-tenant access is not permitted.'

    def has_permission(self, request, view):
        return request.user is not None and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if getattr(user, 'is_superuser', False):
            return True

        if check_permission(user, 'tenant_admin'):
            # Tenant admins restricted to their own tenant.
            user_tenant = getattr(user, 'tenant_id', None)
            obj_tenant = getattr(obj, 'tenant_id', None)
            return obj_tenant is None or obj_tenant == user_tenant

        request_tenant = getattr(request, 'tenant', None)
        request_tenant_id = request_tenant.pk if request_tenant else None
        obj_tenant_id = getattr(obj, 'tenant_id', None)
        return obj_tenant_id is None or obj_tenant_id == request_tenant_id


# Backward-compat alias.
IsSameDomainOrAdmin = IsSameTenantOrAdmin


class ReadOnly(BasePermission):
    """Allows GET, HEAD, OPTIONS requests only.

    Intended for composition with ``|`` in DRF permission classes list.
    """

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS
