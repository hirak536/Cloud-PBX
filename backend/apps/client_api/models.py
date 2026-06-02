import hashlib
import hmac
import secrets
import uuid
from django.db import models
from django.conf import settings
from core.models import Tenant


class TenantAPIKey(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='api_keys')
    label = models.CharField(max_length=128)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    # Webhook config — accepts one URL or multiple URLs separated by commas; all receive events.
    webhook_url = models.TextField(blank=True, default='')
    webhook_secret = models.CharField(max_length=256, blank=True)

    @property
    def webhook_urls(self):
        """Return configured webhook URL(s) as a clean list."""
        return [u.strip() for u in (self.webhook_url or '').split(',') if u.strip()]

    # Key stored as SHA-256 hash; plaintext shown only once on generation
    key_hash = models.CharField(max_length=64, unique=True, db_index=True)

    class Meta:
        db_table = 'v_tenant_api_keys'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.label} ({self.tenant.tenant_code})'

    @classmethod
    def generate(cls, tenant, label, created_by=None, **kwargs):
        """Generate a new key. Returns (instance, plaintext_key). Plaintext not stored."""
        plaintext = secrets.token_urlsafe(40)
        key_hash = hashlib.sha256(plaintext.encode()).hexdigest()
        # Set _plaintext before create so the post_save signal can include it
        # in the api_key.created webhook payload.
        instance = cls(
            tenant=tenant,
            label=label,
            created_by=created_by,
            key_hash=key_hash,
            **kwargs,
        )
        instance._plaintext = plaintext
        instance.save()
        return instance, plaintext

    @classmethod
    def authenticate(cls, plaintext_key):
        """Return active TenantAPIKey for the given plaintext key, or None."""
        from django.utils import timezone
        key_hash = hashlib.sha256(plaintext_key.encode()).hexdigest()
        try:
            obj = cls.objects.select_related('tenant').get(key_hash=key_hash, is_active=True)
        except cls.DoesNotExist:
            return None
        if obj.expires_at and obj.expires_at < timezone.now().date():
            return None
        return obj

    def sign_payload(self, payload_bytes):
        """Return HMAC-SHA256 hex signature of payload using webhook_secret."""
        if not self.webhook_secret:
            return ''
        return hmac.new(
            self.webhook_secret.encode(),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()


class MasterAPIKey(models.Model):
    """Single master key — not tenant-scoped, can only list tenants."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    label = models.CharField(max_length=128, default='Master Key')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    key_hash = models.CharField(max_length=64, unique=True, db_index=True)

    class Meta:
        db_table = 'v_master_api_keys'

    def __str__(self):
        return self.label

    @classmethod
    def generate(cls, label='Master Key', created_by=None):
        """Generate the master key. Returns (instance, plaintext_key)."""
        plaintext = secrets.token_urlsafe(40)
        key_hash = hashlib.sha256(plaintext.encode()).hexdigest()
        instance = cls.objects.create(label=label, created_by=created_by, key_hash=key_hash)
        return instance, plaintext

    @classmethod
    def authenticate(cls, plaintext_key):
        """Return active MasterAPIKey for the given plaintext key, or None."""
        key_hash = hashlib.sha256(plaintext_key.encode()).hexdigest()
        try:
            return cls.objects.get(key_hash=key_hash, is_active=True)
        except cls.DoesNotExist:
            return None


class WebhookDelivery(models.Model):
    """Audit log of webhook delivery attempts."""
    STATUS_PENDING = 'pending'
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_SUCCESS, 'Success'),
        (STATUS_FAILED, 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    api_key = models.ForeignKey(TenantAPIKey, on_delete=models.CASCADE, related_name='deliveries')
    url = models.TextField(blank=True, default='')
    event = models.CharField(max_length=64)
    payload = models.JSONField()
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_response_code = models.IntegerField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'v_webhook_deliveries'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['api_key', 'status']),
            models.Index(fields=['event', 'created_at']),
        ]
