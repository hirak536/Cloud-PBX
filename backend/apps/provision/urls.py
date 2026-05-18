from django.urls import path
from .views import ProvisionView

urlpatterns = [
    path('<str:mac>/', ProvisionView.as_view(), name='provision'),
]
