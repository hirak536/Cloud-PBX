from django.contrib import admin
from .models import FollowMe, FollowMeDestination

class FollowMeDestinationInline(admin.TabularInline):
    model = FollowMeDestination
    extra = 1

@admin.register(FollowMe)
class FollowMeAdmin(admin.ModelAdmin):
    list_display = ['follow_me_name', 'follow_me_context']
    search_fields = ['follow_me_name']
    inlines = [FollowMeDestinationInline]
