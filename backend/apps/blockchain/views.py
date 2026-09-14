import os

from django.conf import settings
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView
from web3 import Web3

from apps.common.permissions import HasPermissionCode

from .models import BlockchainEvent, BlockchainTransaction
from .serializers import BlockchainEventSerializer, BlockchainTransactionSerializer


class TransactionListView(generics.ListAPIView):
    queryset = BlockchainTransaction.objects.all()
    serializer_class = BlockchainTransactionSerializer
    permission_classes = [HasPermissionCode]
    permission_code = "blockchain.view"


class EventListView(generics.ListAPIView):
    queryset = BlockchainEvent.objects.all()
    serializer_class = BlockchainEventSerializer
    permission_classes = [HasPermissionCode]
    permission_code = "blockchain.view"


class BlockchainHealthView(APIView):
    permission_classes = [HasPermissionCode]
    permission_code = "blockchain.health"

    def get(self, request):
        urls = os.getenv(
            "BESU_RPC_URLS",
            "http://besu-validator-1:8545,http://besu-validator-2:8545,http://besu-validator-3:8545,http://besu-validator-4:8545",
        ).split(",")
        validators = []
        for index, url in enumerate(urls, 1):
            try:
                web3 = Web3(Web3.HTTPProvider(url, request_kwargs={"timeout": 3}))
                connected = web3.is_connected()
                validators.append({"validator": index, "rpc": url, "healthy": connected, "block_height": web3.eth.block_number if connected else None})
            except Exception:
                validators.append({"validator": index, "rpc": url, "healthy": False, "block_height": None})
        return Response({"chain_id": settings.CHAIN_ID, "healthy": all(v["healthy"] for v in validators), "validators": validators})

