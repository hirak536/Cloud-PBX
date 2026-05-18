import uuid
from django.db import models
from core.models import Domain

class AccessControl(models.Model):
    ACCESS_DEFAULT_ACTIONS = [('allow', 'Allow'), ('deny', 'Deny')]

    access_control_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
    access_control_name = models.CharField(max_length=255)
    access_control_default = models.CharField(max_length=10, choices=ACCESS_DEFAULT_ACTIONS, default='deny')
    access_control_description = models.TextField(blank=True)
    insert_date = models.DateTimeField(auto_now_add=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_access_controls'

    def __str__(self):
        return self.access_control_name

class AccessControlNode(models.Model):
    NODE_TYPES = [('allow', 'Allow'), ('deny', 'Deny')]

    access_control_node_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    access_control = models.ForeignKey(AccessControl, on_delete=models.CASCADE, related_name='nodes', db_column='access_control_uuid')
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, blank=True, db_column='domain_uuid')
    access_control_node_type = models.CharField(max_length=10, choices=NODE_TYPES, default='allow')
    access_control_node_cidr = models.CharField(max_length=255)
    access_control_node_domain = models.CharField(max_length=255, blank=True)
    access_control_node_description = models.TextField(blank=True)
    insert_date = models.DateTimeField(auto_now_add=True)
    insert_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_access_control_nodes'
