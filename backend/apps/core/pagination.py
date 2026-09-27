"""Shared pagination for list endpoints under /api/v1/."""

from __future__ import annotations

from rest_framework.pagination import PageNumberPagination


class StandardPageNumberPagination(PageNumberPagination):
    """
    Page-number pagination with an explicit page size cap.

    Query conventions:
    - page: 1-based page index
    - page_size: items per page (max 100)
    """

    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100
