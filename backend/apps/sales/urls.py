from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.sales.views import SaleReturnViewSet, SaleViewSet

router = DefaultRouter()
router.register("sales", SaleViewSet, basename="sale")
router.register("sale-returns", SaleReturnViewSet, basename="sale-return")

urlpatterns = [path("", include(router.urls))]
