from django.apps import AppConfig


class FreeswitchConfigConfig(AppConfig):
    name = 'freeswitch_config'
    label = 'freeswitch_config'
    verbose_name = 'FreeSWITCH Config'

    def ready(self):
        from freeswitch_config.signals import register_signals
        register_signals()
