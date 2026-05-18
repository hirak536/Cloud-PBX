from django.urls import path
from .views import XmlCurlView, CdrIngestView, CacheFlushView

urlpatterns = [
    path('', XmlCurlView.as_view(), name='xml-curl'),
    path('cdr/', CdrIngestView.as_view(), name='cdr-ingest'),
    path('cache/flush/', CacheFlushView.as_view(), name='cache-flush'),
]
