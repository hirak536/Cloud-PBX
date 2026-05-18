from django.contrib import admin
from .models import AccessControl, AccessControlNode

class AccessControlNodeInline(admin.TabularInline):
    model = AccessControlNode
    extra = 1

@admin.register(AccessControl)
class AccessControlAdmin(admin.ModelAdmin):
    list_display = ['access_control_name', 'access_control_default']
    search_fields = ['access_control_name']
    inlines = [AccessControlNodeInline]
