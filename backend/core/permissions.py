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
# Per-user action grants
# ---------------------------------------------------------------------------
# The per-page action grants stored on ``User.allowed_actions`` use frontend
# page keys × canonical actions (view/add/edit/delete). The DRF viewsets, on the
# other hand, gate on FusionPBX-style permission strings (``extension_add``,
# ``ivr_menu_delete``, …). This registry bridges the two so a per-user grant can
# satisfy a viewset's ``action_permissions`` check regardless of the app-specific
# prefix. Only the pages opted into action-level control are listed; permission
# strings not present here are never satisfied by ``allowed_actions`` and fall
# back to group-based checks (unchanged behavior).
#
# Shape: permission_string -> (page_key, action)
ACTION_PERMISSION_REGISTRY = {}


def _register_page_actions(page_key, prefix):
    """Map ``{prefix}_{view,add,edit,delete}`` permission strings to (page, action)."""
    for action in ('view', 'add', 'edit', 'delete'):
        ACTION_PERMISSION_REGISTRY[f'{prefix}_{action}'] = (page_key, action)


# page_key (matches the frontend route/allowed_pages key) -> permission prefix
_PAGE_PERMISSION_PREFIXES = {
    'extensions':    'extension',
    'ring-groups':   'ring_group',
    'ivr-menus':     'ivr_menu',
    'call-flows':    'call_flow',
    'destinations':  'destination',
    'voicemails':    'voicemail',
    'call-centers':  'call_center',
    'conferences':   'conferences',
    'working-hours': 'working_hours',
}
for _page, _prefix in _PAGE_PERMISSION_PREFIXES.items():
    _register_page_actions(_page, _prefix)


def user_action_allowed(user, permission_name: str) -> bool:
    """True if *user*'s per-user ``allowed_actions`` grants ``permission_name``.

    Returns False for permission strings not covered by the action registry, so
    callers can fall through to group-based checks. Never grants for the empty
    string.
    """
    mapping = ACTION_PERMISSION_REGISTRY.get(permission_name)
    if not mapping:
        return False
    page, action = mapping
    grants = getattr(user, 'allowed_actions', None) or {}
    page_actions = grants.get(page) or []
    return action in page_actions


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

    # Per-user action grants (allowed_actions) can satisfy action-level
    # permission strings without group membership. Group permissions below
    # remain a valid alternative source.
    if user_action_allowed(user, permission_name):
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
        # Tenant-scoped admins are modeled via the ``admin_tenants`` M2M
        # (UserTenantAccess), not group permissions. Recognize them here so the
        # serializer/UI notion of "Admin" matches this gate. Object-level tenant
        # scoping is enforced separately in the affected viewsets.
        if user.admin_tenants.exists():
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
        # Superusers and staff admins bypass action-level gating: per-user action
        # grants only constrain standard (non-staff) users, mirroring how
        # allowed_pages works. Admins retain full access to every action.
        if getattr(user, 'is_superuser', False) or getattr(user, 'is_staff', False):
            return True

        # Action-level map takes priority (ViewSet actions). The map may live on
        # the permission subclass (e.g. ExtensionPermission.action_permissions)
        # or be overridden per-view; prefer the view, then this instance.
        action_permissions = (
            getattr(view, 'action_permissions', None)
            or getattr(self, 'action_permissions', None)
            or {}
        )
        action = getattr(view, 'action', None)
        if action and action in action_permissions:
            required = action_permissions[action]
            if required == '':
                return True
            return check_permission(user, required)

        # Fall back to a single required_permission (view first, then instance).
        required = (
            getattr(view, 'required_permission', None)
            if getattr(view, 'required_permission', None) is not None
            else getattr(self, 'required_permission', None)
        )
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


class IsStaffOrReadOnly(BasePermission):
    """Read for any authenticated user; write only for staff/superusers.

    Mirrors the frontend role tiers (superuser/admin = ``is_staff``/``is_superuser``;
    standard ``user`` has neither). Standard users get a read-only view; only
    admins and superusers may create, update, or delete.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return bool(getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False))
