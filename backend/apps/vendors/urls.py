from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.vendors.views import VendorViewSet

router = DefaultRouter()
router.register("vendors", VendorViewSet, basename="vendor")

urlpatterns = [path("", include(router.urls))]
