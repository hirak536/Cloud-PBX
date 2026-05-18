import uuid
from django.db import models
from core.models import Domain


class CallCenter(models.Model):
    STRATEGY_CHOICES = [
        ('ring-all','Ring All'),('longest-idle-agent','Longest Idle Agent'),
        ('round-robin','Round Robin'),('top-down','Top Down'),
        ('agent-with-least-talk-time','Least Talk Time'),
        ('agent-with-fewest-calls','Fewest Calls'),
        ('sequentially-by-agent-order','Sequential'),('random','Random'),
    ]
    queue_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, db_column='domain_uuid', related_name='call_centers')
    queue_name = models.CharField(max_length=128)
    queue_extension = models.CharField(max_length=32, blank=True, default='')
    queue_greet_long = models.CharField(max_length=256, blank=True, default='')
    queue_greet_short = models.CharField(max_length=256, blank=True, default='')
    queue_moh_sound = models.CharField(max_length=256, blank=True, default='')
    queue_time_base_score = models.CharField(max_length=16, default='queue')
    queue_max_wait_time = models.IntegerField(default=0)
    queue_max_wait_time_with_no_agent = models.IntegerField(default=0)
    queue_timeout_action = models.CharField(max_length=256, blank=True, default='')
    queue_discard_abandoned_after = models.IntegerField(default=900)
    queue_abandoned_resume_allowed = models.BooleanField(default=False)
    strategy = models.CharField(max_length=64, choices=STRATEGY_CHOICES, default='round-robin')
    queue_tier_rules_apply = models.BooleanField(default=False)
    queue_tier_rule_wait_second = models.IntegerField(default=300)
    queue_tier_rule_no_agent_no_wait = models.BooleanField(default=False)
    queue_tier_rule_wait_multiply_level = models.BooleanField(default=True)
    enabled = models.BooleanField(default=True)
    description = models.TextField(blank=True, default='')
    insert_date = models.DateTimeField(auto_now_add=True, null=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True, null=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_call_center_queues'
        unique_together = [('tenant', 'queue_name')]

    def __str__(self):
        return self.queue_name


class CallCenterAgent(models.Model):
    agent_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, db_column='domain_uuid', related_name='call_center_agents')
    agent_name = models.CharField(max_length=128)
    agent_type = models.CharField(max_length=32, default='callback',
        choices=[('callback','Callback'),('uuid-standby','UUID Standby')])
    agent_contact = models.CharField(max_length=256, blank=True, default='')
    agent_status = models.CharField(max_length=32, default='Available')
    agent_state = models.CharField(max_length=32, default='Waiting')
    max_no_answer = models.IntegerField(default=3)
    wrap_up_time = models.IntegerField(default=10)
    reject_delay_time = models.IntegerField(default=10)
    busy_delay_time = models.IntegerField(default=10)
    no_answer_delay_time = models.IntegerField(default=10)
    enabled = models.BooleanField(default=True)
    description = models.TextField(blank=True, default='')
    insert_date = models.DateTimeField(auto_now_add=True, null=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True, null=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_call_center_agents'
        unique_together = [('tenant', 'agent_name')]

    def __str__(self):
        return self.agent_name


class CallCenterTier(models.Model):
    tier_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, db_column='domain_uuid')
    call_center = models.ForeignKey(CallCenter, on_delete=models.CASCADE,
                                    db_column='queue_uuid', related_name='tiers')
    agent = models.ForeignKey(CallCenterAgent, on_delete=models.CASCADE,
                              db_column='agent_uuid', related_name='tiers')
    tier_agent = models.CharField(max_length=128, blank=True, default='')
    tier_level = models.IntegerField(default=1)
    tier_position = models.IntegerField(default=1)

    class Meta:
        db_table = 'v_call_center_tiers'
        unique_together = [('call_center', 'agent')]
