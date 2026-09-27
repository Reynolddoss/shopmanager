from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.customers.views import CustomerTypeViewSet, CustomerViewSet

router = DefaultRouter()
router.register("customer-types", CustomerTypeViewSet, basename="customer-type")
router.register("customers", CustomerViewSet, basename="customer")

urlpatterns = [path("", include(router.urls))]
