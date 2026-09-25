from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

admin.site.site_header = "ChainControl Administration"
admin.site.site_title = "ChainControl Admin"
admin.site.index_title = "Governance operations"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/token/", TokenObtainPairView.as_view(), name="token"),
    path("api/v1/auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.identities.urls")),
    path("api/v1/", include("apps.assets.urls")),
    path("api/v1/", include("apps.inventory.urls")),
    path("api/v1/", include("apps.blockchain.urls")),
    path("api/v1/", include("apps.audit.urls")),
]
