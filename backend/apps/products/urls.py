from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.products.views import (
    BrandViewSet,
    CategoryViewSet,
    ProductVendorViewSet,
    ProductViewSet,
    SubcategoryViewSet,
    TagViewSet,
    UnitViewSet,
)

router = DefaultRouter()
router.register("categories", CategoryViewSet, basename="category")
router.register("subcategories", SubcategoryViewSet, basename="subcategory")
router.register("brands", BrandViewSet, basename="brand")
router.register("units", UnitViewSet, basename="unit")
router.register("tags", TagViewSet, basename="tag")
router.register("products", ProductViewSet, basename="product")
router.register("product-vendors", ProductVendorViewSet, basename="product-vendor")

urlpatterns = [
    path("", include(router.urls)),
]
