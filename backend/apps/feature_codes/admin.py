from django.contrib import admin
from .models import FeatureCode

@admin.register(FeatureCode)
class FeatureCodeAdmin(admin.ModelAdmin):
    list_display = ['feature_code_name', 'feature_code_key', 'feature_code_number',
                    'feature_code_enabled', 'tenant']
    list_filter = ['feature_code_enabled', 'tenant']
    search_fields = ['feature_code_name', 'feature_code_key', 'feature_code_number']
