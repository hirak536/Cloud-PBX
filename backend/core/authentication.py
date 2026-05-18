import logging

from django.contrib.auth.backends import ModelBackend

from .models import Domain, Tenant, User, UserLog

logger = logging.getLogger(__name__)


class DatabaseAuthBackend(ModelBackend):
    """Authenticates against the v_users table with tenant or domain scoping.

    Supported username formats:
      - Plain:          username='alice'
      - Compound:       username='alice@example.com'  (legacy domain scoping)

    Tenant scoping (preferred):
      Pass tenant_code='ACME' to scope the lookup to a specific tenant.

    Domain scoping (legacy backward compat):
      Pass domain='example.com' or use 'user@domain' username format.

    Global (superuser):
      Pass neither tenant_code nor domain — falls back to username-only lookup.
    """

    def authenticate(self, request, username=None, password=None,
                     domain=None, tenant_code=None, **kwargs):
        if not username or not password:
            return None

        # If the username contains '@', first try it as a literal username
        # (e.g. the username was stored as an email address).  Only fall back
        # to the legacy user@domain split if the literal lookup finds nothing.
        if '@' in username and not domain and not tenant_code:
            # Try as literal username first, then as email, then legacy user@domain split
            user = self._get_user(username, domain=None, tenant_code=None)
            if user is None:
                user = self._get_user_by_email(username)
            if user is None:
                parts = username.rsplit('@', 1)
                user = self._get_user(parts[0], domain=parts[1], tenant_code=None)
        else:
            user = self._get_user(username, domain=domain, tenant_code=tenant_code)

        if user is None:
            # Run the default hasher to mitigate timing attacks.
            User().set_password(password)
            return None

        if not user.check_password(password):
            self._write_log(request, user, log_type='failed',
                            message='Incorrect password.')
            return None

        self._write_log(request, user, log_type='login',
                        message='Successful authentication.')
        return user

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def user_can_authenticate(self, user):
        return getattr(user, 'user_enabled', True)

    def _get_user_by_email(self, email):
        """Fetch a single active user by email address."""
        try:
            return User.objects.get(user_email__iexact=email, user_enabled=True)
        except User.DoesNotExist:
            return None
        except User.MultipleObjectsReturned:
            logger.warning('DatabaseAuthBackend: multiple users share email %r.', email)
            return None

    def _get_user(self, username, domain=None, tenant_code=None):
        """Fetch a single active User, scoped by tenant_code, domain, or globally."""
        try:
            if tenant_code:
                # New preferred path: scope by tenant_code
                try:
                    Tenant.objects.get(tenant_code=tenant_code, tenant_enabled=True)
                except Tenant.DoesNotExist:
                    logger.debug('DatabaseAuthBackend: tenant %r not found or disabled.', tenant_code)
                    return None
                return User.objects.get(
                    username=username,
                    tenant__tenant_code=tenant_code,
                    tenant__tenant_enabled=True,
                    user_enabled=True,
                )
            elif domain:
                # Legacy path: scope by domain name
                try:
                    domain_obj = Domain.objects.get(domain_name=domain, domain_enabled=True)
                except Domain.DoesNotExist:
                    logger.debug('DatabaseAuthBackend: domain %r not found or disabled.', domain)
                    return None
                return User.objects.get(
                    username=username,
                    domain=domain_obj,
                    user_enabled=True,
                )
            else:
                # Global search — useful for superusers with no tenant binding.
                return User.objects.get(username=username, user_enabled=True)
        except User.DoesNotExist:
            logger.debug(
                'DatabaseAuthBackend: user %r not found (tenant_code=%r, domain=%r).',
                username, tenant_code, domain,
            )
            return None
        except User.MultipleObjectsReturned:
            logger.warning(
                'DatabaseAuthBackend: multiple active users named %r exist; '
                'supply tenant_code to disambiguate.',
                username,
            )
            return None

    @staticmethod
    def _get_client_ip(request):
        """Extract the best-guess IPv4 address from the request."""
        if request is None:
            return None
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # Take the leftmost address (client); strip whitespace.
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        # Basic guard: only store plausible IPv4 strings.
        if ip and len(ip) <= 15 and ip.count('.') == 3:
            return ip
        return None

    @staticmethod
    def _get_user_agent(request):
        if request is None:
            return ''
        return request.META.get('HTTP_USER_AGENT', '')

    def _write_log(self, request, user, log_type, message):
        """Persist an authentication event to v_user_logs."""
        try:
            UserLog.objects.create(
                tenant=user.tenant if user else None,
                domain=user.domain if user else None,
                user=user,
                username=user.username if user else '',
                user_log_type=log_type,
                user_log_ipv4=self._get_client_ip(request),
                user_log_agent=self._get_user_agent(request),
                user_log_message=message,
            )
        except Exception:
            # Never let log-writing break authentication.
            logger.exception('DatabaseAuthBackend: failed to write user log.')

    def get_user(self, user_uuid):
        """Required by Django's authentication framework."""
        try:
            return User.objects.get(pk=user_uuid)
        except User.DoesNotExist:
            return None

    # ------------------------------------------------------------------
    # Permission checks delegated to the model helpers
    # ------------------------------------------------------------------

    def has_perm(self, user_obj, perm, obj=None):
        if not user_obj.is_active if hasattr(user_obj, 'is_active') else not user_obj.user_enabled:
            return False
        if user_obj.is_superuser:
            return True
        # perm can be 'app_label.codename' or just 'permission_name'.
        permission_name = perm.split('.')[-1] if '.' in perm else perm
        return permission_name in user_obj.get_permission_names()

    def has_module_perms(self, user_obj, app_label):
        if user_obj.is_superuser:
            return True
        return False


class APIKeyAuthBackend:
    """Allows authentication via the api_key field stored on v_users.

    Used primarily for machine-to-machine API calls.  Pass the key in the
    ``Authorization: ApiKey <key>`` header, or as the ``api_key`` query
    parameter.  The backend does NOT support Django admin login.
    """

    def authenticate(self, request, api_key=None, **kwargs):
        if api_key is None and request is not None:
            api_key = self._extract_key(request)
        if not api_key:
            return None

        try:
            user = User.objects.get(api_key=api_key, user_enabled=True)
        except User.DoesNotExist:
            return None
        except User.MultipleObjectsReturned:
            logger.warning('APIKeyAuthBackend: multiple users share the same api_key.')
            return None

        return user

    @staticmethod
    def _extract_key(request):
        """Try to extract an API key from the Authorization header or query string."""
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.lower().startswith('apikey '):
            return auth_header[7:].strip()
        return request.GET.get('api_key') or request.POST.get('api_key')

    def get_user(self, user_uuid):
        try:
            return User.objects.get(pk=user_uuid)
        except User.DoesNotExist:
            return None
