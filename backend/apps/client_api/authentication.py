from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import MasterAPIKey, TenantAPIKey


class TenantAPIKeyAuthentication(BaseAuthentication):
    """
    Authenticate requests using 'Authorization: ApiKey <key>' header.
    Sets request.auth to the TenantAPIKey instance.
    Uses a dummy AnonymousAPIKeyUser so DRF's IsAuthenticated passes.
    """

    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('ApiKey '):
            return None

        plaintext = auth_header[len('ApiKey '):]
        if not plaintext:
            return None

        api_key = TenantAPIKey.authenticate(plaintext)
        if api_key is None:
            raise AuthenticationFailed('Invalid or expired API key.')

        return (_APIKeyUser(api_key), api_key)

    def authenticate_header(self, request):
        return 'ApiKey realm="client-api"'


class _APIKeyUser:
    """Minimal user-like object so DRF permission checks work."""

    def __init__(self, api_key):
        self.api_key = api_key
        self.tenant = api_key.tenant
        self.is_authenticated = True
        self.is_active = True
        self.is_anonymous = False
        self.is_superuser = False
        self.is_staff = False

    def __str__(self):
        return f'APIKey:{self.api_key.label}'


class MasterAPIKeyAuthentication(BaseAuthentication):
    """
    Authenticate requests using 'Authorization: MasterKey <key>' header.
    """

    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('MasterKey '):
            return None

        plaintext = auth_header[len('MasterKey '):]
        if not plaintext:
            return None

        master_key = MasterAPIKey.authenticate(plaintext)
        if master_key is None:
            raise AuthenticationFailed('Invalid or inactive master key.')

        return (_MasterKeyUser(master_key), master_key)

    def authenticate_header(self, request):
        return 'MasterKey realm="client-api"'


class _MasterKeyUser:
    """Minimal user-like object for master key auth."""

    def __init__(self, master_key):
        self.master_key = master_key
        self.is_authenticated = True
        self.is_active = True
        self.is_anonymous = False
        self.is_superuser = False
        self.is_staff = False

    def __str__(self):
        return f'MasterKey:{self.master_key.label}'
