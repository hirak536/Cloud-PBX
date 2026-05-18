from django.contrib import admin
from .models import Emergency

@admin.register(Emergency)
class EmergencyAdmin(admin.ModelAdmin):
    list_display = ['emergency_number', 'emergency_destination', 'emergency_enabled']
    list_filter = ['emergency_enabled']
    search_fields = ['emergency_number']
