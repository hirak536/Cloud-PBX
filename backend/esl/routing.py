from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'^ws/active-calls/$', consumers.ActiveCallsConsumer.as_asgi()),
    re_path(r'^ws/active-conferences/$', consumers.ActiveConferencesConsumer.as_asgi()),
    re_path(r'^ws/registrations/$', consumers.RegistrationsConsumer.as_asgi()),
    re_path(r'^ws/operator-panel/$', consumers.OperatorPanelConsumer.as_asgi()),
    re_path(r'^ws/extension-status/$', consumers.ExtensionStatusConsumer.as_asgi()),
]
