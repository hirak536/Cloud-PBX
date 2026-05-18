import uuid
from django.db import models

class Module(models.Model):
    module_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    module_label = models.CharField(max_length=255)
    module_name = models.CharField(max_length=255, unique=True)
    module_category = models.CharField(max_length=128, blank=True)
    module_sequence = models.IntegerField(default=100)
    module_enabled = models.BooleanField(default=True)
    module_default_enabled = models.CharField(max_length=10, default='true')
    module_description = models.TextField(blank=True)
    insert_date = models.DateTimeField(auto_now_add=True)
    update_date = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'v_modules'
        ordering = ['module_category', 'module_sequence']

    def __str__(self):
        return self.module_label
