import uuid
from django.db import models
from core.models import Domain

DEST_TYPE_CHOICES = [
    ('extension',          'Extension'),
    ('ring_group',         'Ring Group'),
    ('voicemail',          'Voicemail'),
    ('ivr_menu',           'IVR Menu'),
    ('conference',         'Conference'),
    ('external',           'External Number'),
    ('hangup',             'Hangup'),
    ('custom_destination', 'Custom Destination'),
]

DAY_OF_WEEK_CHOICES = [
    (1, 'Monday'),
    (2, 'Tuesday'),
    (3, 'Wednesday'),
    (4, 'Thursday'),
    (5, 'Friday'),
    (6, 'Saturday'),
    (7, 'Sunday'),
]


class WorkingHours(models.Model):
    working_hours_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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
        null=True,
        blank=True,
        db_column='domain_uuid',
    )
    working_hours_name = models.CharField(max_length=255)
    working_hours_description = models.TextField(blank=True)
    working_hours_enabled = models.BooleanField(default=True)
    dialplan_extension = models.CharField(
        max_length=255,
        blank=True,
        help_text='Dialplan extension matched by FreeSWITCH (e.g. wh_a1b2c3d4). Auto-generated if blank.',
    )
    timezone = models.CharField(
        max_length=64,
        default='UTC',
        help_text='IANA timezone (e.g. America/Chicago) used to evaluate open/close '
                  'windows. Set as the FreeSWITCH `timezone` channel variable so '
                  'time-of-day matching is DST-aware.',
    )

    # Open-hours destination
    open_dest_type = models.CharField(
        max_length=64,
        choices=DEST_TYPE_CHOICES,
        default='hangup',
        help_text='Where to route calls during open hours.',
    )
    open_dest_target_uuid = models.UUIDField(
        null=True,
        blank=True,
        help_text='UUID of the open-hours destination object (Extension, Ring Group, etc.).',
    )
    open_dest_external_number = models.CharField(
        max_length=255,
        blank=True,
        help_text='External number for open-hours routing (used when dest_type=external).',
    )

    # Closed-hours destination
    closed_dest_type = models.CharField(
        max_length=64,
        choices=DEST_TYPE_CHOICES,
        default='hangup',
        help_text='Where to route calls outside open hours.',
    )
    closed_dest_target_uuid = models.UUIDField(
        null=True,
        blank=True,
        help_text='UUID of the closed-hours destination object.',
    )
    closed_dest_external_number = models.CharField(
        max_length=255,
        blank=True,
        help_text='External number for closed-hours routing (used when dest_type=external).',
    )

    insert_date = models.DateTimeField(auto_now_add=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_working_hours'

    def __str__(self):
        return self.working_hours_name

    def save(self, *args, **kwargs):
        if not self.dialplan_extension:
            self.dialplan_extension = 'wh_' + str(self.working_hours_uuid).replace('-', '')[:8]
        super().save(*args, **kwargs)


class WorkingHoursDay(models.Model):
    """Per-day schedule entry for a WorkingHours profile."""

    day_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    working_hours = models.ForeignKey(
        WorkingHours,
        on_delete=models.CASCADE,
        related_name='days',
        db_column='working_hours_uuid',
    )
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    day_of_week = models.IntegerField(
        choices=DAY_OF_WEEK_CHOICES,
        help_text='1=Monday, 7=Sunday.',
    )
    is_open = models.BooleanField(
        default=True,
        help_text='Whether this is a working day.',
    )
    open_time = models.TimeField(
        null=True,
        blank=True,
        help_text='Start of working hours (e.g. 09:00).',
    )
    close_time = models.TimeField(
        null=True,
        blank=True,
        help_text='End of working hours (e.g. 17:00).',
    )

    class Meta:
        db_table = 'v_working_hours_days'
        ordering = ['day_of_week', 'open_time']
        indexes = [
            models.Index(fields=['working_hours', 'day_of_week']),
        ]

    def __str__(self):
        day_name = dict(DAY_OF_WEEK_CHOICES).get(self.day_of_week, str(self.day_of_week))
        if self.is_open and self.open_time and self.close_time:
            return f'{day_name}: {self.open_time:%H:%M}–{self.close_time:%H:%M}'
        return f'{day_name}: Closed'


class WorkingHoursHoliday(models.Model):
    """Holiday exception — calls always route to the closed destination on this date."""

    holiday_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    working_hours = models.ForeignKey(
        WorkingHours,
        on_delete=models.CASCADE,
        related_name='holidays',
        db_column='working_hours_uuid',
    )
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    holiday_date = models.DateField(help_text='Date of the holiday (YYYY-MM-DD).')
    holiday_name = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = 'v_working_hours_holidays'
        ordering = ['holiday_date']
        indexes = [
            models.Index(fields=['working_hours', 'holiday_date']),
        ]

    def __str__(self):
        return f'{self.holiday_date}: {self.holiday_name or "Holiday"}'
