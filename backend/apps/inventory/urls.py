from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CatalogItemViewSet, CatalogVariantViewSet, InventoryCategoryViewSet, InventoryLocationViewSet, InventoryMovementViewSet, InventoryRequestViewSet, InventoryStockViewSet, InventorySubcategoryViewSet

router = DefaultRouter()
router.register("inventory/categories", InventoryCategoryViewSet, basename="inventory-category")
router.register("inventory/subcategories", InventorySubcategoryViewSet, basename="inventory-subcategory")
router.register("inventory/catalog", CatalogItemViewSet, basename="inventory-catalog")
router.register("inventory/variants", CatalogVariantViewSet, basename="inventory-variant")
router.register("inventory/locations", InventoryLocationViewSet, basename="inventory-location")
router.register("inventory/stocks", InventoryStockViewSet, basename="inventory-stock")
router.register("inventory/requests", InventoryRequestViewSet, basename="inventory-request")
router.register("inventory/movements", InventoryMovementViewSet, basename="inventory-movement")

urlpatterns = [path("", include(router.urls))]

