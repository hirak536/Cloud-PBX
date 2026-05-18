from django.contrib import admin
from .models import Gateway
from .views import _write_gateway_file, _delete_gateway_file


@admin.register(Gateway)
class GatewayAdmin(admin.ModelAdmin):
    list_display = ['gateway', 'domain', 'proxy', 'register', 'gateway_enabled']
    list_filter = ['gateway_enabled', 'register', 'profile']
    search_fields = ['gateway', 'proxy', 'realm']

    def save_model(self, request, obj, form, change):
        old_name = None
        old_profile = None
        if change and 'gateway' in form.changed_data:
            old_name = form.initial.get('gateway')
            old_profile = form.initial.get('profile') or 'external'
        super().save_model(request, obj, form, change)
        if old_name and old_name != obj.gateway:
            _delete_gateway_file(old_name, old_profile)
        _write_gateway_file(obj)
        self._trigger_reload(obj, old_name, old_profile)

    def delete_model(self, request, obj):
        name = obj.gateway
        profile = obj.profile or 'external'
        super().delete_model(request, obj)
        _delete_gateway_file(name, profile)
        self._trigger_killgw(name, profile)

    def _trigger_reload(self, gw, old_name=None, old_profile=None):
        try:
            from esl.tasks import sofia_killgw_and_rescan, sofia_profile_rescan
            if old_name:
                sofia_killgw_and_rescan.delay(old_name, old_profile or 'external')
            sofia_killgw_and_rescan.delay(gw.gateway, gw.profile or 'external')
        except Exception:
            pass

    def _trigger_killgw(self, name, profile):
        try:
            from esl.tasks import sofia_killgw_and_rescan
            sofia_killgw_and_rescan.delay(name, profile)
        except Exception:
            pass
