"""
Root URL configuration.

All public HTTP APIs are versioned under /api/v1/ so a future cloud backend
can keep the same contract while adding /api/v2/ without breaking the desktop UI.
Everything else falls through to the built React app.
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

from apps.core.frontend_views import FrontendAppView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.core.urls")),
    path("api/v1/", include("apps.products.urls")),
    path("api/v1/", include("apps.vendors.urls")),
    path("api/v1/", include("apps.customers.urls")),
    path("api/v1/", include("apps.inventory.urls")),
    path("api/v1/", include("apps.purchases.urls")),
    path("api/v1/", include("apps.sales.urls")),
    path("api/v1/", include("apps.payments.urls")),
    path("api/v1/", include("apps.expenses.urls")),
    path("api/v1/", include("apps.analytics.urls")),
    # Product photos. Served directly (also with DEBUG off) because this API
    # only answers requests from this computer.
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
    # React app shell and assets; API/admin/media prefixes never reach it.
    re_path(r"^(?P<path>(?!api/|admin/|media/).*)$", FrontendAppView.as_view(), name="frontend-app"),
]
