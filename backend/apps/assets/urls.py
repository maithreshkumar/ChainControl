from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AssetViewSet, TransferViewSet

router = DefaultRouter()
router.register("assets", AssetViewSet, basename="asset")
router.register("transfers", TransferViewSet, basename="transfer")

urlpatterns = [path("", include(router.urls))]

