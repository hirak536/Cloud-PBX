"""Core API views for FusionPBX-Django.

Provides:
  - JWT-based login / logout / token-refresh / me endpoints
  - CRUD ViewSets for Domain, User, Group, GroupPermission, UserGroup,
    UserSetting, UserLog (read-only), DefaultSetting, DomainSetting
"""

import logging
import secrets
import string
from urllib.parse import urlencode

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from apps.common.email_templates import password_reset_email, forgot_password_email, welcome_email
from django.db import IntegrityError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .mixins import write_audit_log, _capture_changes
from . import cache_version
from .models import (
    AuditLog,
    DefaultSetting,
    Domain,
    DomainSetting,
    Group,
    GroupPermission,
    Tenant,
    User,
    UserGroup,
    UserLog,
    UserSetting,
)
from .permissions import (
    HasPBXPermission,
    IsDomainAdmin,
    IsOwnerOrAdmin,
    IsSameDomainOrAdmin,
    IsSuperAdmin,
    IsTenantAdmin,
    check_permission,
)
from .serializers import (
    AuditLogSerializer,
    DefaultSettingSerializer,
    DomainSerializer,
    DomainSettingSerializer,
    GroupPermissionSerializer,
    GroupSerializer,
    LoginSerializer,
    MeSerializer,
    TenantListSerializer,
    TenantSerializer,
    UserCreateSerializer,
    UserGroupSerializer,
    UserLogSerializer,
    UserSerializer,
    UserSettingSerializer,
    UserUpdateSerializer,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _get_client_ip(request) -> str | None:
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    if ip and len(ip) <= 15 and ip.count('.') == 3:
        return ip
    return None


def _get_user_agent(request) -> str:
    return request.META.get('HTTP_USER_AGENT', '')


def _create_user_log(user, log_type, request, message=''):
    """Write a UserLog row; silently swallow errors so auth is not broken."""
    try:
        UserLog.objects.create(
            domain=user.domain if user else None,
            user=user,
            username=user.username if user else '',
            user_log_type=log_type,
            user_log_ipv4=_get_client_ip(request),
            user_log_agent=_get_user_agent(request),
            user_log_message=message,
        )
    except Exception:
        logger.exception('Failed to create UserLog entry.')


def _tokens_for_user(user):
    """Return a dict with refresh and access JWT strings."""
    refresh = RefreshToken.for_user(user)
    # Embed custom claims useful for the frontend.
    refresh['username'] = user.username
    refresh['tenant_uuid'] = str(user.tenant_id) if user.tenant_id else None
    refresh['tenant_code'] = user.tenant.tenant_code if user.tenant_id else None
    refresh['domain'] = str(user.domain_id) if user.domain_id else None
    refresh['is_superuser'] = user.is_superuser
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


# ---------------------------------------------------------------------------
# Auth views
# ---------------------------------------------------------------------------

class LoginView(APIView):
    """POST /auth/login/

    Accepts JSON body::

        {
            "username": "alice",
            "password": "secret",
            "domain": "example.com"   // optional; can be part of username
        }

    Returns JWT access + refresh tokens together with a user summary on
    success.  Failed attempts are logged to v_user_logs.
    """

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            # Log failed attempt if we have enough data to identify the user.
            username = request.data.get('username', '')
            domain = request.data.get('domain', '')
            UserLog.objects.create(
                user=None,
                username=username,
                user_log_type='failed',
                user_log_ipv4=_get_client_ip(request),
                user_log_agent=_get_user_agent(request),
                user_log_message='Login validation failed.',
            )
            return Response(serializer.errors, status=status.HTTP_401_UNAUTHORIZED)

        user = serializer.validated_data['user']
        tokens = _tokens_for_user(user)
        _create_user_log(user, 'login', request, 'JWT login.')

        user_data = UserSerializer(user, context={'request': request}).data
        return Response(
            {
                'access': tokens['access'],
                'refresh': tokens['refresh'],
                'user': user_data,
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    """POST /auth/logout/

    Body::

        {"refresh": "<refresh_token>"}

    Blacklists the provided refresh token (requires
    ``rest_framework_simplejwt.token_blacklist`` in INSTALLED_APPS).
    Creates a logout entry in v_user_logs.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response(
                {'detail': 'Refresh token is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        _create_user_log(request.user, 'logout', request, 'JWT logout.')
        return Response({'detail': 'Successfully logged out.'}, status=status.HTTP_200_OK)


class MeView(APIView):
    """GET /auth/me/

    Returns the authenticated user's profile, groups, and permission names.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = MeSerializer(request.user, context={'request': request})
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# Password management views
# ---------------------------------------------------------------------------

class ResetPasswordView(APIView):
    """POST /auth/reset-password/  — admin resets a user's password, sends email with temp password."""
    permission_classes = [IsAuthenticated, IsDomainAdmin]

    def post(self, request):
        user_uuid = request.data.get('user_uuid')
        if not user_uuid:
            return Response({'detail': 'user_uuid is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user = User.objects.get(pk=user_uuid)
        except User.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Generate temp password
        alphabet = string.ascii_letters + string.digits + '!@#$%'
        temp_password = ''.join(secrets.choice(alphabet) for _ in range(12))
        user.set_password(temp_password)
        user.must_change_password = True
        user.save(update_fields=['password', 'must_change_password', 'update_date'])

        # Send email
        email_error = None
        if user.user_email:
            try:
                name = user.full_name or user.username
                login_url = f"{settings.FRONTEND_URL}/login?{urlencode({'email': user.user_email})}"
                html_body = password_reset_email(name, temp_password, login_url=login_url)
                msg = EmailMultiAlternatives(
                    subject='Your Temporary Password — IHS PBX',
                    body=f'Hello {name},\n\nYour password has been reset. Temporary password: {temp_password}\n\nYou must change it on first login.\n\n— IHS PBX Admin',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[user.user_email],
                )
                msg.attach_alternative(html_body, 'text/html')
                msg.send(fail_silently=False)
            except Exception as e:
                logger.exception('Failed to send reset password email.')
                email_error = str(e)

        if email_error:
            return Response({
                'detail': f'Password reset but email failed: {email_error}',
                'temp_password': temp_password,
            })
        return Response({'detail': 'Password reset. Temporary password sent to user email.'})


class ForgotPasswordView(APIView):
    """POST /auth/forgot-password/  — public endpoint, sends reset email if user exists."""
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        email = request.data.get('email', '').strip()
        if not email:
            return Response({'detail': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)

        # Always return success to prevent user enumeration
        try:
            user = User.objects.filter(user_email__iexact=email, user_enabled=True).first()
            if user:
                alphabet = string.ascii_letters + string.digits + '!@#$%'
                temp_password = ''.join(secrets.choice(alphabet) for _ in range(12))
                user.set_password(temp_password)
                user.must_change_password = True
                user.save(update_fields=['password', 'must_change_password', 'update_date'])
                name = user.full_name or user.username
                login_url = f"{settings.FRONTEND_URL}/login?{urlencode({'email': user.user_email})}"
                html_body = forgot_password_email(name, temp_password, login_url=login_url)
                msg = EmailMultiAlternatives(
                    subject='Password Reset Request — IHS PBX',
                    body=f'Hello {name},\n\nYour temporary password is: {temp_password}\n\nYou must change it on first login.\n\nIf you did not request this, contact your administrator.\n\n— IHS PBX',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[user.user_email],
                )
                msg.attach_alternative(html_body, 'text/html')
                msg.send(fail_silently=False)
        except Exception:
            logger.exception('Failed in forgot-password flow.')

        return Response({'detail': 'If an account with that email exists, a reset email has been sent.'})


class ChangePasswordView(APIView):
    """POST /auth/change-password/  — authenticated user changes their own password."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        current = request.data.get('current_password', '')
        new_password = request.data.get('new_password', '')
        confirm = request.data.get('confirm_password', '')

        if not new_password or len(new_password) < 8:
            return Response({'detail': 'New password must be at least 8 characters.'}, status=status.HTTP_400_BAD_REQUEST)
        if new_password != confirm:
            return Response({'detail': 'Passwords do not match.'}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        # Skip current password check if must_change_password (they may have a temp password)
        if not user.must_change_password:
            if not user.check_password(current):
                return Response({'detail': 'Current password is incorrect.'}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.must_change_password = False
        user.save(update_fields=['password', 'must_change_password', 'update_date'])
        return Response({'detail': 'Password changed successfully.'})


# ---------------------------------------------------------------------------
# Tenant ViewSet
# ---------------------------------------------------------------------------

class TenantViewSet(viewsets.ModelViewSet):
    """CRUD for v_tenants.

    Superadmins can create, update, and delete tenants.
    Tenant admins can view and update their own tenant only.
    """

    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get_serializer_class(self):
        if self.action == 'list':
            return TenantListSerializer
        return TenantSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Tenant.objects.all().order_by('tenant_code')
        if user.tenant_id:
            return Tenant.objects.filter(pk=user.tenant_id)
        return Tenant.objects.none()

    def get_permissions(self):
        # Any authenticated user may list/retrieve tenants they can see — the
        # queryset already scopes non-superusers to their own tenant. This lets
        # the sidebar resolve the user's Active Tenant. Writes stay admin-only.
        if self.action == 'list':
            return [IsAuthenticated()]
        if self.action in ('retrieve', 'update', 'partial_update'):
            return [IsAuthenticated(), IsTenantAdmin()]
        return [IsAuthenticated(), IsSuperAdmin()]

    def perform_create(self, serializer):
        serializer.save(insert_user=self.request.user.pk)
        tenant = serializer.instance
        write_audit_log(self.request, 'create', tenant)
        self._provision_api_key(tenant)

    def _provision_api_key(self, tenant):
        """Auto-generate an API key for a newly created tenant and POST it to the provisioning webhook."""
        import requests
        from apps.client_api.models import TenantAPIKey
        logger_local = logging.getLogger(__name__)
        webhook_urls = tenant.provisioning_webhook_urls
        # Store the first URL on the API key for backward compatibility with per-key webhook fan-out.
        primary_url = webhook_urls[0] if webhook_urls else ''
        try:
            api_key_instance, plaintext = TenantAPIKey.generate(
                tenant=tenant,
                label='Auto-generated on tenant creation',
                webhook_url=primary_url,
            )
        except Exception:
            logger_local.exception('Failed to auto-generate API key for tenant %s', tenant.tenant_code)
            return

        if not webhook_urls:
            return

        payload = {
            'event': 'tenant.created',
            'tenant_uuid': str(tenant.tenant_uuid),
            'tenant_code': tenant.tenant_code,
            'tenant_name': tenant.tenant_name,
            'api_key': plaintext,
            'api_key_id': str(api_key_instance.id),
        }
        for url in webhook_urls:
            try:
                resp = requests.post(
                    url,
                    json=payload,
                    timeout=10,
                    headers={'Content-Type': 'application/json'},
                )
                logger_local.info(
                    'Provisioning webhook for tenant %s → %s (%s)',
                    tenant.tenant_code, url, resp.status_code,
                )
            except Exception:
                logger_local.exception(
                    'Provisioning webhook failed for tenant %s → %s',
                    tenant.tenant_code, url,
                )

    def perform_update(self, serializer):
        changes = _capture_changes(serializer.instance, serializer.validated_data)
        serializer.save(update_user=self.request.user.pk)
        write_audit_log(self.request, 'update', serializer.instance, changes=changes)

    @action(detail=True, methods=['post'], url_path='apply-recording')
    def apply_recording(self, request, pk=None):
        """Bulk-apply the tenant's recording_enabled flag to all extensions."""
        tenant = self.get_object()
        from apps.extensions.models import Extension
        value = 'all' if tenant.recording_enabled else ''
        updated = Extension.objects.filter(tenant=tenant).update(user_record=value)
        return Response(
            {'detail': f'Recording setting applied to {updated} extension(s).'},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=['post'], url_path='apply-push-notifications')
    def apply_push_notifications(self, request, pk=None):
        """Bulk-apply the tenant's push_notifications_enabled flag to all extensions."""
        tenant = self.get_object()
        from apps.extensions.models import Extension
        value = tenant.push_notifications_enabled
        updated = Extension.objects.filter(tenant=tenant).update(mobile_push_enabled=value)
        
        # Invalidate FreeSWITCH config cache
        from freeswitch_config.signals import _invalidate_dialplan_all, _invalidate_directory_all
        try:
            _invalidate_dialplan_all()
            _invalidate_directory_all()
        except Exception:
            logger.exception('Failed to invalidate FreeSWITCH cache after applying push notifications.')

        return Response(
            {'detail': f'Push notifications setting applied to {updated} extension(s).'},
            status=status.HTTP_200_OK,
        )


    def destroy(self, request, *args, **kwargs):
        tenant = self.get_object()
        if tenant.domains.exists():
            return Response(
                {'detail': 'Cannot delete a tenant that still has domains.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        write_audit_log(request, 'delete', tenant)
        return super().destroy(request, *args, **kwargs)


# ---------------------------------------------------------------------------
# Domain ViewSet
# ---------------------------------------------------------------------------

class DomainViewSet(viewsets.ModelViewSet):
    """CRUD for v_domains.

    Only superadmins can create or delete domains.
    Domain admins can list and retrieve domains (their own).
    """

    serializer_class = DomainSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Domain.objects.all().order_by('domain_name')
        # Domain admins can see their own domain only.
        if user.domain_id:
            return Domain.objects.filter(pk=user.domain_id)
        return Domain.objects.none()

    def perform_create(self, serializer):
        serializer.save(insert_user=self.request.user.pk)
        write_audit_log(self.request, 'create', serializer.instance)

    def perform_update(self, serializer):
        changes = _capture_changes(serializer.instance, serializer.validated_data)
        serializer.save(update_user=self.request.user.pk)
        write_audit_log(self.request, 'update', serializer.instance, changes=changes)

    def destroy(self, request, *args, **kwargs):
        domain = self.get_object()
        if domain.domain_name == getattr(settings, 'PBX_DEFAULT_DOMAIN', None):
            return Response(
                {'detail': 'The default domain cannot be deleted.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        write_audit_log(request, 'delete', domain)
        return super().destroy(request, *args, **kwargs)


# ---------------------------------------------------------------------------
# User ViewSet
# ---------------------------------------------------------------------------

class UserViewSet(viewsets.ModelViewSet):
    """CRUD for v_users, scoped to the current domain.

    Superadmins can see all users across all domains.
    Domain admins can manage users within their own domain.
    Regular users can only read their own record.
    """

    permission_classes = [IsAuthenticated, IsDomainAdmin]

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        if self.action in ('update', 'partial_update'):
            return UserUpdateSerializer
        return UserSerializer

    def get_queryset(self):
        user = self.request.user

        # Optional tenant scoping via ?tenant=<uuid>, applied on top of the
        # role-based queryset. Lets the Users page list only the selected
        # tenant's users.
        tenant_filter = self.request.query_params.get('tenant')

        if user.is_superuser:
            qs = User.objects.select_related('tenant', 'domain').prefetch_related(
                'user_groups__group', 'admin_tenants'
            ).order_by('domain', 'username')
            if tenant_filter:
                qs = qs.filter(tenant_id=tenant_filter)
            return qs

        if check_permission(user, 'domain_admin') and user.domain_id:
            qs = User.objects.filter(domain_id=user.domain_id).select_related(
                'tenant', 'domain'
            ).prefetch_related('user_groups__group', 'admin_tenants').order_by('username')
            if tenant_filter:
                qs = qs.filter(tenant_id=tenant_filter)
            return qs

        # Regular users — return only themselves.
        return User.objects.filter(pk=user.pk).select_related('tenant', 'domain').prefetch_related(
            'user_groups__group', 'admin_tenants'
        )

    def get_permissions(self):
        if self.action in ('retrieve',):
            # Allow users to retrieve their own record.
            return [IsAuthenticated(), IsOwnerOrAdmin()]
        return [perm() for perm in self.permission_classes]

    def perform_create(self, serializer):
        # Generate a temporary password and force change on first login.
        alphabet = string.ascii_letters + string.digits + '!@#$%'
        temp_password = ''.join(secrets.choice(alphabet) for _ in range(12))

        # Auto-assign the current domain if not explicitly provided.
        request_domain = getattr(self.request, 'domain', None)
        if not serializer.validated_data.get('domain') and request_domain:
            user = serializer.save(
                domain=request_domain,
                insert_user=self.request.user.pk,
                must_change_password=True,
            )
        else:
            user = serializer.save(
                insert_user=self.request.user.pk,
                must_change_password=True,
            )

        # Overwrite whatever password the admin typed with our temp password.
        user.set_password(temp_password)
        user.save(update_fields=['password'])

        # Send welcome email if the user has an email address.
        if user.user_email:
            try:
                name = user.full_name or user.username
                login_url = f"{settings.FRONTEND_URL}/login?{urlencode({'email': user.user_email})}"
                html_body = welcome_email(
                    name=name,
                    username=user.username,
                    temp_password=temp_password,
                    login_url=login_url,
                    email=user.user_email,
                )
                msg = EmailMultiAlternatives(
                    subject='Welcome to IHS PBX — Your Account is Ready',
                    body=(
                        f'Hello {name},\n\n'
                        f'Your IHS PBX account has been created.\n\n'
                        f'Username: {user.username}\n'
                        f'Email: {user.user_email}\n'
                        f'Temporary Password: {temp_password}\n\n'
                        f'You must change your password on first login.\n\n'
                        f'Log in at: {settings.FRONTEND_URL}\n\n'
                        f'— IHS PBX Admin'
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[user.user_email],
                )
                msg.attach_alternative(html_body, 'text/html')
                msg.send(fail_silently=False)
            except Exception:
                logger.exception('Failed to send welcome email to %s', user.user_email)

        write_audit_log(self.request, 'create', user)

    def perform_update(self, serializer):
        changes = _capture_changes(serializer.instance, serializer.validated_data)
        serializer.save(update_user=self.request.user.pk)
        write_audit_log(self.request, 'update', serializer.instance, changes=changes)

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.pk == request.user.pk:
            return Response(
                {'detail': 'You cannot delete your own account.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        write_audit_log(request, 'delete', obj)
        return super().destroy(request, *args, **kwargs)


# ---------------------------------------------------------------------------
# Group ViewSet
# ---------------------------------------------------------------------------

class GroupViewSet(viewsets.ModelViewSet):
    """CRUD for v_groups, domain-scoped."""

    serializer_class = GroupSerializer
    permission_classes = [IsAuthenticated, IsDomainAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Group.objects.select_related('domain').order_by('domain', 'group_name')
        if user.domain_id:
            return Group.objects.filter(
                domain_id=user.domain_id
            ).select_related('domain').order_by('group_name')
        return Group.objects.none()

    def perform_create(self, serializer):
        request_domain = getattr(self.request, 'domain', None)
        if not serializer.validated_data.get('domain') and request_domain:
            serializer.save(domain=request_domain, insert_user=self.request.user.pk)
        else:
            serializer.save(insert_user=self.request.user.pk)
        write_audit_log(self.request, 'create', serializer.instance)

    def perform_update(self, serializer):
        changes = _capture_changes(serializer.instance, serializer.validated_data)
        serializer.save(update_user=self.request.user.pk)
        write_audit_log(self.request, 'update', serializer.instance, changes=changes)

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.group_protected:
            return Response(
                {'detail': 'Protected groups cannot be deleted.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        write_audit_log(request, 'delete', obj)
        return super().destroy(request, *args, **kwargs)


# ---------------------------------------------------------------------------
# GroupPermission ViewSet
# ---------------------------------------------------------------------------

class GroupPermissionViewSet(viewsets.ModelViewSet):
    """CRUD for v_group_permissions."""

    serializer_class = GroupPermissionSerializer
    permission_classes = [IsAuthenticated, IsDomainAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return GroupPermission.objects.select_related('domain', 'group').order_by(
                'group', 'permission_name'
            )
        if user.domain_id:
            return GroupPermission.objects.filter(
                domain_id=user.domain_id
            ).select_related('domain', 'group').order_by('group', 'permission_name')
        return GroupPermission.objects.none()

    def perform_create(self, serializer):
        request_domain = getattr(self.request, 'domain', None)
        if not serializer.validated_data.get('domain') and request_domain:
            serializer.save(domain=request_domain, insert_user=self.request.user.pk)
        else:
            serializer.save(insert_user=self.request.user.pk)
        write_audit_log(self.request, 'create', serializer.instance)


# ---------------------------------------------------------------------------
# UserGroup ViewSet
# ---------------------------------------------------------------------------

class UserGroupViewSet(viewsets.ModelViewSet):
    """Manage v_user_groups (user ↔ group assignments)."""

    serializer_class = UserGroupSerializer
    permission_classes = [IsAuthenticated, IsDomainAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return UserGroup.objects.select_related('user', 'group', 'domain').order_by(
                'user', 'group'
            )
        if user.domain_id:
            return UserGroup.objects.filter(
                domain_id=user.domain_id
            ).select_related('user', 'group', 'domain').order_by('user', 'group')
        return UserGroup.objects.none()

    def perform_create(self, serializer):
        request_domain = getattr(self.request, 'domain', None)
        if not serializer.validated_data.get('domain') and request_domain:
            try:
                serializer.save(domain=request_domain)
            except IntegrityError:
                raise ValidationError({'detail': 'This user is already in that group.'})
        else:
            try:
                serializer.save()
            except IntegrityError:
                raise ValidationError({'detail': 'This user is already in that group.'})


# ---------------------------------------------------------------------------
# UserSetting ViewSet
# ---------------------------------------------------------------------------

class UserSettingViewSet(viewsets.ModelViewSet):
    """CRUD for v_user_settings."""

    serializer_class = UserSettingSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return UserSetting.objects.select_related('user', 'domain').order_by('user')
        if check_permission(user, 'domain_admin') and user.domain_id:
            return UserSetting.objects.filter(
                domain_id=user.domain_id
            ).select_related('user', 'domain').order_by('user')
        # Regular users see only their own settings.
        return UserSetting.objects.filter(user=user).select_related('domain').order_by(
            'user_setting_category', 'user_setting_subcategory'
        )

    def perform_create(self, serializer):
        request_domain = getattr(self.request, 'domain', None)
        if not serializer.validated_data.get('domain') and request_domain:
            serializer.save(domain=request_domain)
        else:
            serializer.save()


# ---------------------------------------------------------------------------
# UserLog ViewSet (read-only)
# ---------------------------------------------------------------------------

class UserLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only list and detail for v_user_logs (audit trail)."""

    serializer_class = UserLogSerializer
    permission_classes = [IsAuthenticated, IsDomainAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return UserLog.objects.select_related('user', 'domain').order_by(
                '-user_log_timestamp'
            )
        if check_permission(user, 'domain_admin') and user.domain_id:
            return UserLog.objects.filter(
                domain_id=user.domain_id
            ).select_related('user', 'domain').order_by('-user_log_timestamp')
        # Regular users see only their own logs.
        return UserLog.objects.filter(user=user).select_related('domain').order_by(
            '-user_log_timestamp'
        )


# ---------------------------------------------------------------------------
# DefaultSetting ViewSet
# ---------------------------------------------------------------------------

class DefaultSettingViewSet(viewsets.ModelViewSet):
    """CRUD for v_default_settings (system-wide, superadmin only)."""

    serializer_class = DefaultSettingSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get_queryset(self):
        return DefaultSetting.objects.order_by(
            'default_setting_category',
            'default_setting_subcategory',
            'default_setting_order',
        )

    def perform_create(self, serializer):
        serializer.save(insert_user=self.request.user.pk)
        write_audit_log(self.request, 'create', serializer.instance)

    def perform_update(self, serializer):
        changes = _capture_changes(serializer.instance, serializer.validated_data)
        serializer.save(update_user=self.request.user.pk)
        write_audit_log(self.request, 'update', serializer.instance, changes=changes)


# ---------------------------------------------------------------------------
# DomainSetting ViewSet
# ---------------------------------------------------------------------------

class DomainSettingViewSet(viewsets.ModelViewSet):
    """CRUD for v_domain_settings, scoped to the current domain."""

    serializer_class = DomainSettingSerializer
    permission_classes = [IsAuthenticated, IsDomainAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return DomainSetting.objects.select_related('domain').order_by(
                'domain',
                'domain_setting_category',
                'domain_setting_subcategory',
                'domain_setting_order',
            )
        if user.domain_id:
            return DomainSetting.objects.filter(
                domain_id=user.domain_id
            ).select_related('domain').order_by(
                'domain_setting_category',
                'domain_setting_subcategory',
                'domain_setting_order',
            )
        return DomainSetting.objects.none()

    def perform_create(self, serializer):
        request_domain = getattr(self.request, 'domain', None)
        if not serializer.validated_data.get('domain') and request_domain:
            serializer.save(
                domain=request_domain,
                insert_user=self.request.user.pk,
            )
        else:
            serializer.save(insert_user=self.request.user.pk)
        write_audit_log(self.request, 'create', serializer.instance)

    def perform_update(self, serializer):
        changes = _capture_changes(serializer.instance, serializer.validated_data)
        serializer.save(update_user=self.request.user.pk)
        write_audit_log(self.request, 'update', serializer.instance, changes=changes)


# ---------------------------------------------------------------------------
# AuditLog ViewSet (read-only)
# ---------------------------------------------------------------------------

class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only list and detail for v_audit_logs (portal change history)."""

    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, IsDomainAdmin]

    def get_queryset(self):
        user = self.request.user
        qs = AuditLog.objects.select_related('user', 'domain', 'tenant').order_by('-timestamp')

        if user.is_superuser:
            pass  # see all
        elif check_permission(user, 'domain_admin') and user.domain_id:
            qs = qs.filter(domain_id=user.domain_id)
        else:
            qs = qs.filter(user=user)

        # Optional filters
        action = self.request.query_params.get('action')
        if action:
            qs = qs.filter(action=action)
        resource_type = self.request.query_params.get('resource_type')
        if resource_type:
            qs = qs.filter(resource_type__iexact=resource_type)
        username = self.request.query_params.get('username')
        if username:
            qs = qs.filter(username__icontains=username)

        return qs


class FlushCacheView(APIView):
    """POST /api/core/cache/flush/ — bump global cache version (superusers only)."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_superuser:
            raise PermissionDenied('Superuser access required.')
        new_version = cache_version.bump()
        return Response({'status': 'ok', 'cache_version': new_version})
