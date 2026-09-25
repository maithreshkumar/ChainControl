import os

from django.conf import settings
from django.db import models
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import UserRole
from apps.assets.models import Asset, TransferRequest
from apps.audit.models import AuditEvent, SecurityAlert
from apps.common.permissions import HasPermissionCode
from apps.identities.models import DecentralizedIdentity
from apps.inventory.models import CatalogItem, InventoryMovement, InventoryRequest, InventoryStock

from .models import BlockchainEvent, BlockchainTransaction
from .client import get_web3
from .observer import block_data, transaction_data, validator_status
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
                validators.append(validator_status(index, url))
            except Exception:
                validators.append({"validator": index, "rpc": url, "healthy": False, "block_height": None, "peer_count": None, "validator_count": None, "validator_addresses": []})
        heights = [row["block_height"] for row in validators if row["block_height"] is not None]
        healthy = all(row["healthy"] for row in validators)
        consensus_healthy = healthy and bool(heights) and max(heights) - min(heights) <= 1 and all(row["validator_count"] == 4 for row in validators)
        return Response({"chain_id": settings.CHAIN_ID, "healthy": healthy, "consensus_healthy": consensus_healthy, "latest_block": max(heights) if heights else None, "validators": validators})


class ObserverBlockListView(APIView):
    permission_classes = [HasPermissionCode]
    permission_code = "observer.view"

    def get(self, request):
        web3 = get_web3()
        latest = web3.eth.block_number
        try:
            before = min(int(request.query_params.get("before", latest)), latest)
            limit = min(max(int(request.query_params.get("limit", 20)), 1), 50)
        except ValueError:
            return Response({"error": {"code": "REQUEST_INVALID", "message": "before and limit must be integers."}}, status=400)
        numbers = range(before, max(before - limit, -1), -1)
        results = [block_data(number, web3=web3) for number in numbers]
        next_before = results[-1]["number"] - 1 if results and results[-1]["number"] > 0 else None
        return Response({"latest": latest, "count": len(results), "next_before": next_before, "results": results})


class ObserverBlockDetailView(APIView):
    permission_classes = [HasPermissionCode]
    permission_code = "observer.view"

    def get(self, request, identifier):
        parsed = int(identifier) if identifier.isdigit() else identifier
        return Response(block_data(parsed, include_all=True))


class ObserverTransactionDetailView(APIView):
    permission_classes = [HasPermissionCode]
    permission_code = "observer.view"

    def get(self, request, tx_hash):
        return Response(transaction_data(tx_hash))


class ObserverNFTListView(APIView):
    permission_classes = [HasPermissionCode]
    permission_code = "observer.view"

    def get(self, request):
        assets = Asset.objects.filter(token_id__isnull=False).select_related("owner_projection", "owner_projection__user", "department").prefetch_related("versions__integrity_checks", "transfers").order_by("token_id")[:200]
        mint_transactions = {row.related_object_id: row.tx_hash for row in BlockchainTransaction.objects.filter(operation="ASSET_MINT", related_object_type="Asset", related_object_id__in=[str(asset.id) for asset in assets], tx_hash__isnull=False).order_by("created_at")}
        results = [{
            "asset_id": str(asset.id),
            "token_id": asset.token_id,
            "name": asset.name,
            "asset_type": asset.asset_type,
            "state": asset.state,
            "department": asset.department.code if asset.department else None,
            "owner_did": asset.owner_projection.did if asset.owner_projection else None,
            "owner_username": asset.owner_projection.user.username if asset.owner_projection else None,
            "integrity": "PASSED" if any(check.passed for version in asset.versions.all() for check in version.integrity_checks.all()) else "NOT_VERIFIED",
            "transfer_count": sum(1 for transfer in asset.transfers.all() if transfer.state == TransferRequest.State.COMPLETED),
            "mint_transaction": mint_transactions.get(str(asset.id)),
        } for asset in assets]
        return Response({"count": len(results), "results": results})


class ObserverNFTDetailView(APIView):
    permission_classes = [HasPermissionCode]
    permission_code = "observer.view"

    def get(self, request, token_id):
        asset = Asset.objects.filter(token_id=token_id).select_related("owner_projection", "owner_projection__user", "department").prefetch_related("versions__integrity_checks", "transfers__sender__user", "transfers__recipient__user", "transfers__blockchain_transaction").first()
        if asset is None:
            return Response({"error": {"code": "NFT_NOT_FOUND", "message": "NFT-backed asset was not found."}}, status=404)
        mint = BlockchainTransaction.objects.filter(operation="ASSET_MINT", related_object_type="Asset", related_object_id=str(asset.id)).order_by("-created_at").first()
        transfer_ids = [str(row.id) for row in asset.transfers.all()]
        chain_transactions = BlockchainTransaction.objects.filter(
            models.Q(id=mint.id) if mint else models.Q(pk__isnull=True)
        ) | BlockchainTransaction.objects.filter(related_object_type="TransferRequest", related_object_id__in=transfer_ids)
        chain_transactions = chain_transactions.distinct().order_by("block_number", "created_at")
        on_chain_owner = None
        try:
            from .contracts import get_contract
            _, contract = get_contract("AssetRegistry")
            on_chain_owner = contract.functions.ownerOf(token_id).call()
        except Exception:
            pass
        versions = [{
            "version": version.version, "content_hash": version.content_hash, "metadata_hash": version.metadata_hash,
            "size": version.size, "mime_type": version.mime_type,
            "integrity": [{"passed": check.passed, "calculated_hash": check.calculated_hash, "error_code": check.error_code, "checked_at": check.created_at} for check in version.integrity_checks.all()],
        } for version in asset.versions.all()]
        transfers = [{
            "id": str(row.id), "state": row.state, "sender": row.sender.user.username, "sender_did": row.sender.did,
            "recipient": row.recipient.user.username, "recipient_did": row.recipient.did,
            "transaction_hash": row.blockchain_transaction.tx_hash if row.blockchain_transaction else None, "created_at": row.created_at,
        } for row in asset.transfers.all()]
        transactions = [{"hash": row.tx_hash, "operation": row.operation, "status": row.status, "block_number": row.block_number} for row in chain_transactions if row.tx_hash]
        return Response({
            "asset_id": str(asset.id), "token_id": asset.token_id, "name": asset.name, "asset_type": asset.asset_type,
            "serial_number": asset.serial_number, "custody_identifier": asset.custody_identifier, "classification": asset.classification,
            "department": asset.department.code if asset.department else None, "state": asset.state,
            "projected_owner": asset.owner_projection.controller_address if asset.owner_projection else None,
            "blockchain_owner": on_chain_owner, "owner_did": asset.owner_projection.did if asset.owner_projection else None,
            "owner_username": asset.owner_projection.user.username if asset.owner_projection else None,
            "mint_transaction": mint.tx_hash if mint else None, "versions": versions, "transfers": transfers,
            "transactions": transactions, "associated_blocks": sorted({row["block_number"] for row in transactions if row["block_number"] is not None}),
        })


class ObserverAnalyticsView(APIView):
    permission_classes = [HasPermissionCode]
    permission_code = "observer.view"

    def get(self, request):
        web3 = get_web3()
        stocks = list(InventoryStock.objects.all())
        type_counts = {row["asset_type"]: row["count"] for row in CatalogItem.objects.values("asset_type").annotate(count=models.Count("id"))}
        return Response({
            "identities": {"total": DecentralizedIdentity.objects.count(), "active": DecentralizedIdentity.objects.filter(state="ACTIVE").count(), "by_status": list(DecentralizedIdentity.objects.values("state").annotate(count=models.Count("id")).order_by("state"))},
            "roles": list(UserRole.objects.filter(active=True).values("role__code").annotate(count=models.Count("id")).order_by("role__code")),
            "catalog": {"items": CatalogItem.objects.filter(active=True).count(), "stock_locations": len(stocks), "low_stock": sum(1 for stock in stocks if stock.low_stock), "by_type": type_counts, "available": sum(stock.quantity_available for stock in stocks), "issued": sum(stock.quantity_issued for stock in stocks)},
            "assets": {"total": Asset.objects.count(), "nfts": Asset.objects.filter(token_id__isnull=False).count(), "digital": Asset.objects.filter(asset_type=Asset.AssetType.DIGITAL_ASSET).count(), "physical": Asset.objects.filter(asset_type=Asset.AssetType.UNIQUE_PHYSICAL_ASSET).count(), "by_state": list(Asset.objects.values("state").annotate(count=models.Count("id")).order_by("state")), "by_department": list(Asset.objects.values("department__code").annotate(count=models.Count("id")).order_by("department__code"))},
            "requests": {"total": InventoryRequest.objects.count(), "pending": InventoryRequest.objects.filter(status__in=["REQUESTED", "PENDING_APPROVAL", "RESERVED"]).count(), "most_requested": list(InventoryRequest.objects.values("variant__sku", "variant__item__name").annotate(quantity=models.Sum("quantity")).order_by("-quantity")[:8])},
            "movements": list(InventoryMovement.objects.values("movement_type").annotate(quantity=models.Sum("quantity"), count=models.Count("id")).order_by("movement_type")),
            "blockchain": {"latest_block": web3.eth.block_number, "indexed_transactions": BlockchainTransaction.objects.count(), "indexed_events": BlockchainEvent.objects.count()},
            "security": {"alerts": SecurityAlert.objects.count(), "failed_operations": AuditEvent.objects.exclude(outcome="SUCCESS").count(), "transfer_count": TransferRequest.objects.filter(state=TransferRequest.State.COMPLETED).count()},
        })


class ObserverSearchView(APIView):
    permission_classes = [HasPermissionCode]
    permission_code = "observer.view"

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        if not query:
            return Response({"results": []})
        results = []
        if query.isdigit():
            try:
                block = block_data(int(query))
                results.append({"type": "block", "id": str(block["number"]), "label": f"Block #{block['number']}", "detail": block["hash"]})
            except Exception:
                pass
            for asset in Asset.objects.filter(token_id=int(query))[:10]:
                results.append({"type": "nft", "id": str(asset.token_id), "label": f"NFT #{asset.token_id}", "detail": asset.name})
        if len(query) in {64, 66}:
            try:
                detail = transaction_data(query)
                results.append({"type": "transaction", "id": detail["hash"], "label": "Transaction", "detail": detail["decoded"]["function"] or detail["hash"]})
            except Exception:
                try:
                    block = block_data(query)
                    results.append({"type": "block", "id": str(block["number"]), "label": f"Block #{block['number']}", "detail": block["hash"]})
                except Exception:
                    pass
        identities = DecentralizedIdentity.objects.filter(models.Q(did__icontains=query) | models.Q(controller_address__icontains=query)).select_related("user")[:10]
        results.extend({"type": "identity", "id": str(row.id), "label": row.user.username, "detail": row.did} for row in identities)
        assets = Asset.objects.filter(models.Q(name__icontains=query) | models.Q(serial_number__icontains=query))
        try:
            assets = assets | Asset.objects.filter(id=query)
        except Exception:
            pass
        results.extend({"type": "asset", "id": str(row.id), "label": row.name, "detail": f"NFT #{row.token_id}" if row.token_id else row.state} for row in assets.distinct()[:10])
        return Response({"results": results[:30]})
