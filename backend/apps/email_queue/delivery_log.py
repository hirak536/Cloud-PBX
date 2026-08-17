"""EmailDelivery — durable record of every outbound email.

Two kinds of sender coexist in this project and neither alone gives full history:

  * Queued mail (account/password mail) goes through DatabaseEmailBackend into
    v_email_queue. That table is a *send queue* — it carries no attachment info
    and rows are mutated in place as they drain, so it is not an audit trail.
  * Attachment mail (fax, voicemail) talks to SMTP directly via a private
    get_connection() precisely because DatabaseEmailBackend drops attachments.
    Those sends previously left no trace beyond a logger.info line.

This model records both, written at the moment of the send attempt, so failures
are captured as well as successes. Bodies are stored for diagnosis but are
scrubbed of credentials first — see log_email_attempt.
"""

import uuid

from django.db import models


class EmailDelivery(models.Model):
    STATUS_SENT = 'sent'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_SENT, 'Sent'),
        (STATUS_FAILED, 'Failed'),
    ]

    # Where the send originated, so fax/voicemail history can be filtered out
    # of the general account-mail noise.
    CATEGORY_CHOICES = [
        ('fax_status', 'Fax status'),
        ('fax_inbound', 'Inbound fax'),
        ('voicemail', 'Voicemail'),
        ('account', 'Account'),
        ('queue', 'Queue drain'),
        ('other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )

    category = models.CharField(max_length=32, choices=CATEGORY_CHOICES, default='other')
    # Free-form link back to the originating object (FaxFile uuid, voicemail
    # message uuid, user pk). Not a FK — the referents live in several apps.
    related_uuid = models.CharField(max_length=64, blank=True, default='', db_index=True)

    email_from = models.CharField(max_length=320, blank=True, default='')
    # Recipients are stored joined rather than one row per address: the unit
    # being logged is the send attempt, and a partial SMTP failure fails all.
    email_to = models.TextField(blank=True, default='')
    email_cc = models.TextField(blank=True, default='')
    subject = models.CharField(max_length=512, blank=True, default='')
    body = models.TextField(blank=True, default='')

    # Attachment metadata only — never the bytes. A fax PDF or voicemail WAV
    # would bloat the table and the file already lives on disk.
    attachment_names = models.TextField(blank=True, default='')
    attachment_count = models.PositiveSmallIntegerField(default=0)
    attachment_bytes = models.IntegerField(default=0)

    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_SENT)
    error = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'v_email_deliveries'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['category', 'created_at']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f'{self.email_to}: {self.subject} ({self.status})'
