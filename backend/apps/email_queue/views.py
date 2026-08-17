import logging
from django.core.mail import get_connection, EmailMultiAlternatives
from django.utils import timezone
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from core.mixins import TenantScopedViewSetMixin
from core.permissions import IsSuperAdmin
from .models import EmailQueue, EmailDelivery
from .logging_utils import send_and_log
from .serializers import EmailQueueSerializer, EmailDeliverySerializer

logger = logging.getLogger(__name__)


class EmailQueueViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = EmailQueue.objects.select_related('tenant', 'domain')
    serializer_class = EmailQueueSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['domain', 'email_queue_status']
    search_fields = ['email_queue_to', 'email_queue_subject']
    ordering_fields = ['insert_date', 'email_queue_status']

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, IsSuperAdmin])
    def send_pending(self, request):
        """Send all pending emails using SMTP backend directly."""
        pending = EmailQueue.objects.filter(email_queue_status='pending')
        sent = 0
        failed = 0

        # Use SMTP backend directly regardless of EMAIL_BACKEND setting
        from django.conf import settings
        connection = get_connection(
            backend='django.core.mail.backends.smtp.EmailBackend',
            host=settings.EMAIL_HOST,
            port=settings.EMAIL_PORT,
            username=settings.EMAIL_HOST_USER,
            password=settings.EMAIL_HOST_PASSWORD,
            use_tls=settings.EMAIL_USE_TLS,
            use_ssl=settings.EMAIL_USE_SSL,
            fail_silently=False,
        )

        try:
            connection.open()
            for item in pending:
                try:
                    body = item.email_queue_body or ''
                    is_html = body.strip().startswith('<')
                    msg = EmailMultiAlternatives(
                        subject=item.email_queue_subject,
                        body='Please view this email in an HTML-compatible email client.' if is_html else body,
                        from_email=item.email_queue_from,
                        to=[item.email_queue_to],
                        cc=[c.strip() for c in item.email_queue_cc.split(',') if c.strip()],
                        connection=connection,
                    )
                    if is_html:
                        msg.attach_alternative(body, 'text/html')
                    send_and_log(msg, category='queue', related_uuid=str(item.pk),
                                 tenant=item.tenant)
                    item.email_queue_status = 'sent'
                    item.email_queue_date = timezone.now()
                    item.save(update_fields=['email_queue_status', 'email_queue_date'])
                    sent += 1
                except Exception as e:
                    logger.exception('Failed to send email %s', item.pk)
                    item.email_queue_status = 'failed'
                    item.email_queue_retry_count += 1
                    item.save(update_fields=['email_queue_status', 'email_queue_retry_count'])
                    failed += 1
        finally:
            connection.close()

        return Response({'sent': sent, 'failed': failed})


class EmailDeliveryViewSet(viewsets.ReadOnlyModelViewSet):
    """History of every outbound email — fax, voicemail and account mail alike.

    Read-only by design: this is an audit trail, so there is no create/update
    path. Tenant scoping is done here rather than via TenantScopedViewSetMixin
    because that mixin falls back to a `domain` FK this model does not have.
    """
    serializer_class = EmailDeliverySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'category', 'related_uuid']
    search_fields = ['email_to', 'subject', 'related_uuid']
    ordering_fields = ['created_at', 'status', 'category']
    ordering = ['-created_at']

    def get_queryset(self):
        qs = EmailDelivery.objects.select_related('tenant')
        user = self.request.user
        if user.is_superuser:
            tenant_id = self.request.query_params.get('tenant')
            return qs.filter(tenant_id=tenant_id) if tenant_id else qs
        tenant_id = getattr(user, 'tenant_id', None)
        return qs.filter(tenant_id=tenant_id) if tenant_id else qs.none()
