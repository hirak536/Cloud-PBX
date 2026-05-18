from django.contrib import admin
from .models import CustomDestination

@admin.register(CustomDestination)
class CustomDestinationAdmin(admin.ModelAdmin):
    list_display = ['name', 'dest_type', 'enabled', 'tenant']
    list_filter = ['dest_type', 'enabled']
    search_fields = ['name', 'description']
