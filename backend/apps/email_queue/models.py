import uuid
from django.db import models
from core.models import Domain

class EmailQueue(models.Model):
    STATUSES = [('pending', 'Pending'), ('sent', 'Sent'), ('failed', 'Failed')]

    email_queue_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
    email_queue_from = models.EmailField(blank=True)
    email_queue_to = models.EmailField()
    email_queue_cc = models.EmailField(blank=True)
    email_queue_subject = models.CharField(max_length=512)
    email_queue_body = models.TextField()
    email_queue_status = models.CharField(max_length=20, choices=STATUSES, default='pending')
    email_queue_retry_count = models.IntegerField(default=0)
    email_queue_date = models.DateTimeField(null=True, blank=True)
    insert_date = models.DateTimeField(auto_now_add=True)
    insert_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_email_queue'
        ordering = ['-insert_date']
        indexes = [
            models.Index(fields=['email_queue_status', 'insert_date']),
        ]

    def __str__(self):
        return f'{self.email_queue_to}: {self.email_queue_subject}'
