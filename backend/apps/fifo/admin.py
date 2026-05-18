from django.contrib import admin
from .models import Fifo, FifoCallers

@admin.register(Fifo)
class FifoAdmin(admin.ModelAdmin):
    list_display = ['fifo_name', 'fifo_extension', 'fifo_strategy', 'fifo_enabled']
    list_filter = ['fifo_enabled']
    search_fields = ['fifo_name']
