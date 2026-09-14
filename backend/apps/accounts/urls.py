from django.urls import path

from .views import InvitationActivateView, InvitationCreateView, MeView, WalletProvisionView

urlpatterns = [
    path("me/", MeView.as_view(), name="me"),
    path("invitations/", InvitationCreateView.as_view(), name="invitation-create"),
    path("invitations/activate/", InvitationActivateView.as_view(), name="invitation-activate"),
    path("wallet-provision/", WalletProvisionView.as_view(), name="wallet-provision"),
]
