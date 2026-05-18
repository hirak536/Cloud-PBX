from django.contrib import admin
from .models import IvrMenu, IvrMenuOption

class IvrMenuOptionInline(admin.TabularInline):
    model = IvrMenuOption
    extra = 1

@admin.register(IvrMenu)
class IvrMenuAdmin(admin.ModelAdmin):
    list_display = ['ivr_menu_name', 'ivr_menu_extension', 'ivr_menu_enabled']
    list_filter = ['ivr_menu_enabled']
    search_fields = ['ivr_menu_name']
    inlines = [IvrMenuOptionInline]
