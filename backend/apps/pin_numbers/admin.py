from django.contrib import admin
from .models import PinNumber

@admin.register(PinNumber)
class PinNumberAdmin(admin.ModelAdmin):
    list_display = ['pin_number_enabled', 'pin_number_accountcode', 'insert_date']
    list_filter = ['pin_number_enabled']
