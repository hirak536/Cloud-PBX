import uuid
from django.db import models
from core.models import Domain

class MusicOnHold(models.Model):
    music_on_hold_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
    music_on_hold_name = models.CharField(max_length=255)
    music_on_hold_path = models.CharField(max_length=512, blank=True)
    music_on_hold_rate = models.CharField(max_length=10, default='8000')
    music_on_hold_shuffle = models.BooleanField(default=False)
    music_on_hold_channels = models.IntegerField(default=1)
    music_on_hold_interval = models.IntegerField(default=20)
    music_on_hold_timer_name = models.CharField(max_length=64, blank=True)
    music_on_hold_chime_list = models.TextField(blank=True)
    music_on_hold_chime_freq = models.IntegerField(default=0)
    music_on_hold_chime_max = models.IntegerField(default=0)
    insert_date = models.DateTimeField(auto_now_add=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_music_on_hold'

    def __str__(self):
        return self.music_on_hold_name
