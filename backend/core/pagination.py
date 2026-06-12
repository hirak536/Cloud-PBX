"""Shared DRF pagination.

The frontend uses infinite scroll with a user-selectable page size. The stock
PageNumberPagination ignores a client-supplied page size, so list endpoints were
capped at PAGE_SIZE (25) and callers had to loop to fetch everything. This class
honors a `page_size` query param up to MAX_PAGE_SIZE so the UI's page-size
selector (25 / 50 / 100 / 200) works on every list endpoint.
"""
from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 200
