from django.urls import path

from .views import BlockchainHealthView, EventListView, ObserverAnalyticsView, ObserverBlockDetailView, ObserverBlockListView, ObserverNFTDetailView, ObserverNFTListView, ObserverSearchView, ObserverTransactionDetailView, TransactionListView

urlpatterns = [
    path("blockchain/transactions/", TransactionListView.as_view(), name="blockchain-transactions"),
    path("blockchain/events/", EventListView.as_view(), name="blockchain-events"),
    path("blockchain/health/", BlockchainHealthView.as_view(), name="blockchain-health"),
    path("observer/blocks/", ObserverBlockListView.as_view(), name="observer-blocks"),
    path("observer/blocks/<str:identifier>/", ObserverBlockDetailView.as_view(), name="observer-block-detail"),
    path("observer/transactions/<str:tx_hash>/", ObserverTransactionDetailView.as_view(), name="observer-transaction-detail"),
    path("observer/nfts/", ObserverNFTListView.as_view(), name="observer-nfts"),
    path("observer/nfts/<int:token_id>/", ObserverNFTDetailView.as_view(), name="observer-nft-detail"),
    path("observer/analytics/", ObserverAnalyticsView.as_view(), name="observer-analytics"),
    path("observer/search/", ObserverSearchView.as_view(), name="observer-search"),
]
