from django.contrib import admin
from .models import Module

@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ['module_label', 'module_name', 'module_category', 'module_enabled']
    list_filter = ['module_category', 'module_enabled']
    search_fields = ['module_name', 'module_label']
