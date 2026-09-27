from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.purchases.views import PurchaseReturnViewSet, PurchaseViewSet

router = DefaultRouter()
router.register("purchases", PurchaseViewSet, basename="purchase")
router.register("purchase-returns", PurchaseReturnViewSet, basename="purchase-return")

urlpatterns = [path("", include(router.urls))]
