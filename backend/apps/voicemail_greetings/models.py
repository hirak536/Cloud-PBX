import uuid
from django.db import models
from core.models import Domain

class VoicemailGreeting(models.Model):
    voicemail_greeting_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
    voicemail_id = models.CharField(max_length=255)
    greeting_id = models.IntegerField(default=0)
    greeting_name = models.CharField(max_length=255, blank=True)
    greeting_filename = models.CharField(max_length=512)
    greeting_description = models.TextField(blank=True)
    insert_date = models.DateTimeField(auto_now_add=True)
    insert_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_voicemail_greetings'

    def __str__(self):
        return f'{self.voicemail_id} - {self.greeting_name}'
