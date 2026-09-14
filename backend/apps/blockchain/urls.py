from django.urls import path

from .views import BlockchainHealthView, EventListView, TransactionListView

urlpatterns = [
    path("blockchain/transactions/", TransactionListView.as_view(), name="blockchain-transactions"),
    path("blockchain/events/", EventListView.as_view(), name="blockchain-events"),
    path("blockchain/health/", BlockchainHealthView.as_view(), name="blockchain-health"),
]

