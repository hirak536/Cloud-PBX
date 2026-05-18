from django.contrib import admin
from .models import FeatureCode

@admin.register(FeatureCode)
class FeatureCodeAdmin(admin.ModelAdmin):
    list_display = ['feature_code_name']
    search_fields = ['feature_code_name']
