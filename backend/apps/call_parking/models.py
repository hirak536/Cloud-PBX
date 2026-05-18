import uuid
from django.db import models
from core.models import Domain


TIMEOUT_ACTION_CHOICES = [
    ('hangup',           'Hangup'),
    ('return_to_parker', 'Return to Parker'),
    ('voicemail',        'Send to Voicemail'),
]


class CallParkingSlot(models.Model):
    call_parking_slot_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(
        Domain,
        on_delete=models.CASCADE,
        db_column='domain_uuid',
        related_name='call_parking_slots',
    )
    slot_number = models.IntegerField()
    slot_name = models.CharField(max_length=128, blank=True, default='')
    parking_timeout = models.IntegerField(default=60)
    timeout_action = models.CharField(
        max_length=32,
        choices=TIMEOUT_ACTION_CHOICES,
        default='hangup',
    )
    timeout_voicemail_extension = models.CharField(max_length=32, blank=True, default='')
    # MOH URI — blank = system default ($${hold_music})
    music_on_hold = models.CharField(max_length=255, blank=True, default='')
    slot_enabled = models.BooleanField(default=True)
    is_occupied = models.BooleanField(default=False)
    parked_call_uuid = models.CharField(max_length=255, blank=True, default='')

    insert_date = models.DateTimeField(auto_now_add=True, null=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True, null=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_call_parking_slots'
        unique_together = [('tenant', 'slot_number')]

    def __str__(self):
        return f'{self.slot_number}' + (f' ({self.slot_name})' if self.slot_name else '')
