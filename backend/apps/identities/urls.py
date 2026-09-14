from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ChallengeCreateView, ChallengeVerifyView, IdentityViewSet

router = DefaultRouter()
router.register("identities", IdentityViewSet, basename="identity")

urlpatterns = [
    path("", include(router.urls)),
    path("auth/challenges/", ChallengeCreateView.as_view(), name="challenge-create"),
    path("auth/challenges/verify/", ChallengeVerifyView.as_view(), name="challenge-verify"),
]

