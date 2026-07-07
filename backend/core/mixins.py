"""Shared mixins for tenant-aware ViewSets.

Usage in any app ViewSet::

    from core.mixins import TenantScopedViewSetMixin

    class ExtensionViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
        queryset = Extension.objects.select_related('tenant', 'domain')
        serializer_class = ExtensionSerializer
        # get_queryset, perform_create, caching are handled by the mixin

Tenant scoping is automatic:
- Superusers see all data across tenants
- Regular/admin users see only their own tenant's data
- The mixin falls back to domain filtering for objects not yet migrated

Caching is automatic (Redis via django_redis):
- GET list/detail responses are cached per tenant + query params (default 5 min)
- Any write (create/update/destroy) invalidates that tenant's cached entries
- Set cache_timeout = 0 on a ViewSet to disable caching for that resource
"""

import hashlib
import logging

from django.core.cache import cache
from django.db import IntegrityError
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response

from core import cache_version as _cv

logger = logging.getLogger('cache')
audit_logger = logging.getLogger('audit')


class ClientAPICacheMixin:
    """Cache mixin for client API APIViews (read-only, tenant-scoped by UUID).

    Subclasses set:
        cache_resource (str): Short name used in the cache key (e.g. 'extensions').
        cache_timeout (int): Seconds to cache. Default 300. Set 0 to disable.
    """

    cache_resource: str = 'resource'
    cache_timeout: int = 300

    def _ck(self, tenant_uuid: str, suffix: str) -> str:
        return f'client:{self.cache_resource}:{tenant_uuid}:v{_cv.get()}:{suffix}'

    def _cache_get(self, key: str):
        try:
            return cache.get(key)
        except Exception:
            return None

    def _cache_set(self, key: str, data):
        if not self.cache_timeout:
            return
        try:
            cache.set(key, data, self.cache_timeout)
        except Exception as exc:
            logger.debug('Cache set failed (%s): %s', self.cache_resource, exc)

    def _cache_invalidate(self, tenant_uuid: str):
        if not self.cache_timeout:
            return
        try:
            cache.delete_pattern(f'client:{self.cache_resource}:{tenant_uuid}:*')
        except Exception as exc:
            logger.debug('Cache invalidation failed (%s): %s', self.cache_resource, exc)


# ── Audit helpers ──────────────────────────────────────────────────────────────

def _audit_get_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    if ip and len(ip) <= 15 and ip.count('.') == 3:
        return ip
    return None


def _capture_changes(instance, validated_data):
    """Return {before, after} dict of changed fields only."""
    before, after = {}, {}
    for field, new_val in validated_data.items():
        try:
            old_val = getattr(instance, field, None)
            # Resolve FK instances to their PKs for comparison
            if hasattr(old_val, 'pk'):
                old_val = old_val.pk
            if hasattr(new_val, 'pk'):
                new_val = new_val.pk
            if str(old_val) != str(new_val):
                before[field] = str(old_val) if old_val is not None else None
                after[field] = str(new_val) if new_val is not None else None
        except Exception:
            pass
    return {'before': before, 'after': after} if before else None


def write_audit_log(request, action, instance, changes=None):
    """Write one AuditLog row. Silently swallows errors so writes never break the API."""
    try:
        from core.models import AuditLog  # lazy import to avoid circular deps
        user = getattr(request, 'user', None)
        AuditLog.objects.create(
            tenant=getattr(user, 'tenant', None) if user else None,
            domain=getattr(user, 'domain', None) or getattr(instance, 'domain', None),
            user=user if (user and user.is_authenticated) else None,
            username=user.username if (user and user.is_authenticated) else '',
            action=action,
            resource_type=instance.__class__.__name__,
            resource_uuid=str(instance.pk),
            resource_name=str(instance)[:256],
            changes=changes,
            ip_address=_audit_get_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:512],
        )
    except Exception:
        audit_logger.exception('Failed to write audit log for action=%s resource=%s', action, type(instance).__name__)


class TenantScopedViewSetMixin:
    """Mixin that automatically scopes queryset and perform_create to the
    requesting user's tenant, and caches read responses in Redis.

    Class attributes the ViewSet may override:
        tenant_field (str): FK field name on the model. Default: 'tenant'.
        domain_field (str): Fallback FK for migration transition. Default: 'domain'.
        cache_timeout (int): Seconds to cache list/detail responses. 0 = disabled.
    """

    tenant_field: str = 'tenant'
    domain_field: str = 'domain'
    cache_timeout: int = 300  # 5 minutes; set to 0 on the ViewSet to disable

    # ── Cache helpers ──────────────────────────────────────────────────────────

    def _tenant_cache_id(self) -> str:
        """Return a stable string identifying the tenant scope for this request."""
        user = self.request.user
        if user.is_superuser:
            # Superuser may scope to a specific tenant via ?tenant=<uuid>
            tid = self.request.query_params.get('tenant')
            return f'su:{tid}' if tid else 'su'
        return str(getattr(user, 'tenant_id', None) or 'global')

    def _cache_scope_id(self) -> str:
        """Extra per-request scoping folded into the cache key. Default empty.

        ViewSets that filter get_queryset() by something finer than tenant
        (e.g. per-user fax-box scope) MUST override this, otherwise a cached
        response built for one user leaks to another user in the same tenant.
        """
        return ''

    def _cache_key(self, suffix: str) -> str:
        scope = self._cache_scope_id()
        scope_part = f':{scope}' if scope else ''
        return f'pbx:{self.__class__.__name__}:{self._tenant_cache_id()}{scope_part}:v{_cv.get()}:{suffix}'

    # Map admin ViewSet class name → client API cache resource name
    _CLIENT_CACHE_RESOURCE_MAP = {
        'ExtensionViewSet': 'extensions',
        'DestinationViewSet': 'destinations',
        'FaxViewSet': 'fax',
    }

    def _cache_invalidate(self):
        """Delete all cached responses for this ViewSet + current tenant scope."""
        if not self.cache_timeout:
            return
        try:
            pattern = f'pbx:{self.__class__.__name__}:{self._tenant_cache_id()}:*'
            cache.delete_pattern(pattern)
        except Exception as exc:
            logger.debug('Cache invalidation failed (%s): %s', self.__class__.__name__, exc)
        # Also invalidate the corresponding client API cache for this resource
        resource = self._CLIENT_CACHE_RESOURCE_MAP.get(self.__class__.__name__)
        if resource:
            try:
                tid = self._tenant_cache_id()
                # tid is 'su:<uuid>' for superuser scoped or a tenant uuid string
                tenant_uuid = tid.split(':', 1)[-1] if tid.startswith('su:') else tid
                if tenant_uuid and tenant_uuid != 'su':
                    cache.delete_pattern(f'client:{resource}:{tenant_uuid}:*')
            except Exception as exc:
                logger.debug('Client cache invalidation failed (%s): %s', resource, exc)

    # ── Cached read operations ─────────────────────────────────────────────────

    def list(self, request, *args, **kwargs):
        if not self.cache_timeout:
            return super().list(request, *args, **kwargs)

        qs_hash = hashlib.md5(request.GET.urlencode().encode()).hexdigest()[:8]
        key = self._cache_key(f'list:{qs_hash}')
        hit = cache.get(key)
        if hit is not None:
            return Response(hit)

        response = super().list(request, *args, **kwargs)
        if response.status_code == 200:
            try:
                cache.set(key, response.data, self.cache_timeout)
            except Exception as exc:
                logger.debug('Cache set failed (%s): %s', self.__class__.__name__, exc)
        return response

    def retrieve(self, request, *args, **kwargs):
        if not self.cache_timeout:
            return super().retrieve(request, *args, **kwargs)

        lookup_field = getattr(self, 'lookup_field', 'pk')
        pk = kwargs.get(lookup_field, kwargs.get('pk', 'unknown'))
        key = self._cache_key(f'detail:{pk}')
        hit = cache.get(key)
        if hit is not None:
            return Response(hit)

        response = super().retrieve(request, *args, **kwargs)
        if response.status_code == 200:
            try:
                cache.set(key, response.data, self.cache_timeout)
            except Exception as exc:
                logger.debug('Cache set failed (%s): %s', self.__class__.__name__, exc)
        return response

    # ── Serializer context ────────────────────────────────────────────────────

    def get_serializer_context(self):
        context = super().get_serializer_context()
        user = self.request.user
        tenant = None
        if user.is_superuser:
            tenant_id = self.request.query_params.get('tenant')
            if tenant_id:
                from core.models import Tenant
                tenant = Tenant.objects.filter(tenant_uuid=tenant_id).first()
        if not tenant:
            tenant = getattr(user, 'tenant', None)
        if tenant:
            context['tenant'] = tenant
        return context

    # ── Queryset scoping ───────────────────────────────────────────────────────

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if user.is_superuser:
            # Superusers can scope to a specific tenant via ?tenant=<uuid>
            tenant_id = self.request.query_params.get('tenant')
            if tenant_id:
                return qs.filter(**{f'{self.tenant_field}_id': tenant_id})
            return qs

        # Primary: filter by tenant
        tenant_id = getattr(user, 'tenant_id', None)
        if tenant_id:
            return qs.filter(**{f'{self.tenant_field}_id': tenant_id})

        # Fallback: filter by domain (objects not yet migrated)
        domain_id = getattr(user, 'domain_id', None)
        if domain_id:
            return qs.filter(**{f'{self.domain_field}_id': domain_id})

        return qs.none()

    # ── Write operations (with cache invalidation) ─────────────────────────────

    def perform_create(self, serializer):
        user = self.request.user
        kwargs = {}

        # Auto-assign tenant
        if not serializer.validated_data.get(self.tenant_field):
            tenant = None
            if user.is_superuser:
                # Superusers: use the sidebar-selected tenant (?tenant=<uuid>)
                tenant_id = self.request.query_params.get('tenant')
                if tenant_id:
                    from core.models import Tenant
                    tenant = Tenant.objects.filter(tenant_uuid=tenant_id).first()
            if not tenant:
                tenant = getattr(user, 'tenant', None)
            if tenant:
                kwargs[self.tenant_field] = tenant

        # Auto-assign domain: user's domain, or fall back to universal domain
        if not serializer.validated_data.get(self.domain_field):
            domain = getattr(user, 'domain', None)
            if not domain:
                from core.models import Domain
                domain = Domain.objects.filter(domain_universal=True, domain_enabled=True).first()
            if domain:
                kwargs[self.domain_field] = domain

        # Audit field
        if hasattr(serializer.Meta.model, 'insert_user'):
            kwargs.setdefault('insert_user', getattr(user, 'user_uuid', None))

        try:
            serializer.save(**kwargs)
        except IntegrityError:
            exc = APIException('A record with these details already exists.')
            exc.status_code = status.HTTP_409_CONFLICT
            raise exc
        self._cache_invalidate()
        write_audit_log(self.request, 'create', serializer.instance)

    def perform_update(self, serializer):
        user = self.request.user
        kwargs = {}
        if hasattr(serializer.Meta.model, 'update_user'):
            kwargs['update_user'] = getattr(user, 'user_uuid', None)

        # Preserve tenant and domain: a PUT that omits these fields should not
        # null them out. DRF treats missing nullable FKs as None on full updates.
        instance = serializer.instance
        changes = _capture_changes(instance, serializer.validated_data) if instance else None
        if instance:
            if not serializer.validated_data.get(self.tenant_field):
                if getattr(instance, f'{self.tenant_field}_id', None):
                    kwargs[self.tenant_field] = getattr(instance, self.tenant_field)
            if not serializer.validated_data.get(self.domain_field):
                if getattr(instance, f'{self.domain_field}_id', None):
                    kwargs[self.domain_field] = getattr(instance, self.domain_field)

        try:
            serializer.save(**kwargs)
        except IntegrityError:
            exc = APIException('A record with these details already exists.')
            exc.status_code = status.HTTP_409_CONFLICT
            raise exc
        self._cache_invalidate()
        write_audit_log(self.request, 'update', serializer.instance, changes=changes)

    def perform_destroy(self, instance):
        self._cache_invalidate()
        write_audit_log(self.request, 'delete', instance)
        instance.delete()
