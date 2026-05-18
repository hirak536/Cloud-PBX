from django.contrib import admin
from .models import Variable

@admin.register(Variable)
class VariableAdmin(admin.ModelAdmin):
    list_display = ['variable_name', 'variable_value', 'variable_enabled']
    list_filter = ['variable_enabled']
    search_fields = ['variable_name']
