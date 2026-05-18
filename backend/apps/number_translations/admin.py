from django.contrib import admin
from .models import NumberTranslation, NumberTranslationDetail

class NumberTranslationDetailInline(admin.TabularInline):
    model = NumberTranslationDetail
    extra = 1

@admin.register(NumberTranslation)
class NumberTranslationAdmin(admin.ModelAdmin):
    list_display = ['number_translation_name']
    search_fields = ['number_translation_name']
    inlines = [NumberTranslationDetailInline]
