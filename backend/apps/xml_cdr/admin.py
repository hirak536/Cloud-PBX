from django.contrib import admin
from .models import XmlCdr

@admin.register(XmlCdr)
class XmlCdrAdmin(admin.ModelAdmin):
    list_display = ['caller_id_number', 'destination_number', 'start_stamp', 'billsec', 'hangup_cause', 'direction']
    list_filter = ['direction', 'hangup_cause', 'missed_call', 'domain']
    search_fields = ['caller_id_number', 'caller_id_name', 'destination_number']
    readonly_fields = [f.name for f in XmlCdr._meta.get_fields() if hasattr(f, 'name')]
    date_hierarchy = 'start_stamp'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
