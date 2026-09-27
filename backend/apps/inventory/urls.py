from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.inventory.views import InventoryBatchViewSet, StockMovementViewSet

router = DefaultRouter()
router.register("batches", InventoryBatchViewSet, basename="batch")
router.register("stock-movements", StockMovementViewSet, basename="stock-movement")

urlpatterns = [path("", include(router.urls))]
