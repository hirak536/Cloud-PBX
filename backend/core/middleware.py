import logging
from urllib.parse import parse_qs

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.utils.deprecation import MiddlewareMixin

from .models import Domain

logger = logging.getLogger(__name__)


class NoCacheApiMiddleware(MiddlewareMixin):
    """Stop browsers from heuristically caching API GETs.

    DRF responses carry no Cache-Control header, so browsers apply heuristic
    caching and can serve a stale list right after a create/delete (the deleted
    row keeps showing until a hard refresh). Mark every /api/ response as
    no-store so refetches always hit the server.
    """

    def process_response(self, request, response):
        if request.path.startswith('/api/'):
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response['Pragma'] = 'no-cache'
        return response


class TenantMiddleware(MiddlewareMixin):
    """Resolves the current Tenant from the JWT bearer token and attaches it
    to the request as ``request.tenant``.

    Resolution
    ----------
    1. The ``Authorization: Bearer <token>`` header is decoded using simplejwt.
    2. The ``user_uuid`` claim is extracted and used to load the User.
    3. ``request.tenant`` is set to ``user.tenant`` (or ``None`` for
       unauthenticated requests or superusers with no tenant binding).

    Cache
    -----
    Results are cached per JWT ``jti`` claim to avoid repeated DB hits.
    Call ``TenantMiddleware.invalidate_cache(jti)`` after a user's tenant
    changes, or ``invalidate_cache()`` to flush all.
    """

    _cache: dict = {}  # {jti: Tenant|None}

    def process_request(self, request):
        request.tenant = self._resolve_tenant(request)

    def _resolve_tenant(self, request):
        token_str = self._extract_bearer(request)
        if not token_str:
            return None
        try:
            from rest_framework_simplejwt.tokens import AccessToken
            token = AccessToken(token_str)
            jti = token.get('jti')
            if jti and jti in self.__class__._cache:
                return self.__class__._cache[jti]
            user_uuid = token.get('user_uuid')
            if not user_uuid:
                return None
            from .models import User
            user = User.objects.select_related('tenant').get(
                pk=user_uuid, user_enabled=True
            )
            tenant = user.tenant
            if jti:
                self.__class__._cache[jti] = tenant
            return tenant
        except Exception:
            return None

    @staticmethod
    def _extract_bearer(request):
        auth = request.META.get('HTTP_AUTHORIZATION', '')
        if auth.lower().startswith('bearer '):
            return auth[7:].strip()
        return None

    @classmethod
    def invalidate_cache(cls, jti: str = None):
        if jti:
            cls._cache.pop(jti, None)
        else:
            cls._cache.clear()


class DomainMiddleware(MiddlewareMixin):
    """Detects the current tenant domain from the HTTP_HOST header and
    attaches the corresponding :class:`~core.models.Domain` instance to the
    request as ``request.domain``.

    Resolution order
    ----------------
    1. The ``HTTP_HOST`` header is read and the port is stripped (if any).
    2. The cleaned hostname is looked up against ``v_domains.domain_name``
       (``domain_enabled=True`` only).
    3. If no match is found, the value of the ``PBX_DEFAULT_DOMAIN``
       Django setting is tried as a fallback.
    4. If still unresolved, ``request.domain`` is set to ``None``.

    Configuration
    -------------
    Add to ``MIDDLEWARE`` in settings **before** any view-layer middleware::

        MIDDLEWARE = [
            ...
            'core.middleware.DomainMiddleware',
            ...
        ]

    Optionally set a default domain::

        PBX_DEFAULT_DOMAIN = 'default.example.com'
    """

    # Cache of (hostname -> Domain|None) populated during the process lifetime.
    # This is intentionally a simple in-memory dict; in a multi-process setup
    # each worker maintains its own copy and it is refreshed on next miss after
    # a domain is deleted/renamed.
    _cache: dict = {}

    def process_request(self, request):
        hostname = self._extract_hostname(request)
        domain = self._resolve_domain(hostname)
        request.domain = domain
        if domain is None:
            logger.debug(
                'DomainMiddleware: no domain matched for host %r; request.domain=None.',
                hostname,
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_hostname(request) -> str:
        """Return the hostname portion of HTTP_HOST with port stripped."""
        host = request.META.get('HTTP_HOST', '')
        # Strip port number (both IPv4 host:port and [IPv6]:port forms).
        if host.startswith('['):
            # IPv6 bracketed address, e.g. [::1]:8000
            bracket_end = host.find(']')
            if bracket_end != -1:
                return host[:bracket_end + 1]
            return host
        return host.split(':')[0]

    def _resolve_domain(self, hostname: str):
        """Look up a Domain row, using the instance-level cache."""
        # Try cache first.
        if hostname in self.__class__._cache:
            return self.__class__._cache[hostname]

        domain = self._lookup_domain(hostname)

        if domain is None:
            # Try the configured default domain.
            default_name = getattr(settings, 'PBX_DEFAULT_DOMAIN', None)
            if default_name and default_name != hostname:
                if default_name in self.__class__._cache:
                    domain = self.__class__._cache[default_name]
                else:
                    domain = self._lookup_domain(default_name)
                    self.__class__._cache[default_name] = domain

        # Cache the result (including None) to avoid repeated DB hits.
        self.__class__._cache[hostname] = domain
        return domain

    @staticmethod
    def _lookup_domain(name: str):
        """Query the database for an active domain with the given name."""
        if not name:
            return None
        try:
            return Domain.objects.get(domain_name=name, domain_enabled=True)
        except Domain.DoesNotExist:
            return None

    # ------------------------------------------------------------------
    # Cache invalidation helper (call after Domain saves/deletes)
    # ------------------------------------------------------------------

    @classmethod
    def invalidate_cache(cls, domain_name: str = None):
        """Clear the domain cache.

        Pass a specific ``domain_name`` to remove a single entry, or call
        without arguments to flush the entire cache.
        """
        if domain_name is not None:
            cls._cache.pop(domain_name, None)
        else:
            cls._cache.clear()


class CurrentUserMiddleware(MiddlewareMixin):
    """Attaches the authenticated user's UUID to the thread-local context so
    that model ``insert_user`` / ``update_user`` fields can be populated
    automatically in signals or overridden ``save()`` methods.

    This is a convenience middleware; it is **not** required for basic auth
    to function.

    Usage in a model ``save()``::

        from core.middleware import get_current_user_uuid

        class MyModel(models.Model):
            def save(self, *args, **kwargs):
                uid = get_current_user_uuid()
                if uid and not self.pk:
                    self.insert_user = uid
                super().save(*args, **kwargs)
    """

    import threading
    _local = threading.local()

    def process_request(self, request):
        user = getattr(request, 'user', None)
        if user is not None and hasattr(user, 'user_uuid') and user.is_authenticated:
            self.__class__._local.user_uuid = user.user_uuid
        else:
            self.__class__._local.user_uuid = None

    def process_response(self, request, response):
        self.__class__._local.user_uuid = None
        return response


def get_current_user_uuid():
    """Return the UUID of the currently authenticated request user, or None."""
    return getattr(CurrentUserMiddleware._local, 'user_uuid', None)


class JwtAuthMiddleware:
    """Channels 4 middleware that authenticates WebSocket connections via a JWT
    ``?token=`` query parameter (simplejwt AccessToken).

    Sets ``scope['user']`` before passing to the inner app. Falls back to
    AnonymousUser on any failure so the consumer can handle rejection itself.
    """

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        from channels.db import database_sync_to_async
        scope = dict(scope)
        scope['user'] = await database_sync_to_async(_jwt_get_user)(scope)
        return await self.inner(scope, receive, send)


def _jwt_get_user(scope):
    qs = parse_qs(scope.get('query_string', b'').decode())
    token_list = qs.get('token', [])
    if not token_list:
        return AnonymousUser()
    token_str = token_list[0]
    try:
        from rest_framework_simplejwt.tokens import AccessToken
        from .models import User
        token = AccessToken(token_str)
        user_uuid = token.get('user_uuid')
        if not user_uuid:
            return AnonymousUser()
        return User.objects.select_related('tenant').get(pk=user_uuid, user_enabled=True)
    except Exception:
        return AnonymousUser()


def JwtAuthMiddlewareStack(inner):
    """Convenience wrapper: JWT token auth around AuthMiddlewareStack (session fallback)."""
    from channels.auth import AuthMiddlewareStack
    return JwtAuthMiddleware(AuthMiddlewareStack(inner))
