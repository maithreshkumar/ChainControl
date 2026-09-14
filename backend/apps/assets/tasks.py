from celery import shared_task
from django.db import transaction
from web3 import Web3

from apps.audit.models import SecurityAlert
from apps.audit.services import create_alert
from apps.common.errors import DomainError
from apps.blockchain.transaction_service import TransactionService

from .models import Asset
from .models import TransferRequest


@shared_task(bind=True, autoretry_for=(), max_retries=0)
def submit_asset_mint(self, asset_id: str, correlation_id=None):
    asset = Asset.objects.select_related("owner_projection", "created_by__identity").prefetch_related("versions").get(id=asset_id)
    version = asset.versions.order_by("-version").first()
    recipient = asset.owner_projection or getattr(asset.created_by, "identity", None)
    if recipient is None or recipient.state != "ACTIVE":
        asset.state = Asset.State.REGISTRATION_FAILED
        asset.save(update_fields=["state", "updated_at"])
        raise DomainError("IDENTITY_NOT_ACTIVE", "Mint recipient must have an active identity.")
    try:
        row = TransactionService().submit(
            contract_name="AssetRegistry",
            function_name="mintAsset",
            args=[
                Web3.to_checksum_address(recipient.controller_address),
                Web3.keccak(text=str(asset.id)),
                bytes.fromhex(version.content_hash),
                bytes.fromhex(version.metadata_hash),
            ],
            operation="ASSET_MINT",
            idempotency_key=f"asset-mint:{asset.id}:v{version.version}",
            actor_did=asset.created_by.identity.did,
            related_object_type="Asset",
            related_object_id=asset.id,
            correlation_id=correlation_id or None,
        )
        asset.state = Asset.State.BLOCKCHAIN_PENDING
        asset.save(update_fields=["state", "updated_at"])
        return str(row.id)
    except Exception as exc:
        asset.state = Asset.State.REGISTRATION_FAILED
        asset.save(update_fields=["state", "updated_at"])
        create_alert(alert_type="BLOCKCHAIN_UNAVAILABLE", severity=SecurityAlert.Severity.HIGH, title="Asset registration could not reach blockchain", details={"asset_id": str(asset.id), "error": str(exc)[:500]}, correlation_id=correlation_id or None)
        raise


@shared_task(bind=True, autoretry_for=(), max_retries=0)
def submit_asset_transfer(self, transfer_id: str, correlation_id=None):
    transfer = TransferRequest.objects.select_related("asset", "sender", "recipient").get(id=transfer_id)
    if transfer.state != TransferRequest.State.BLOCKCHAIN_PENDING or transfer.asset.token_id is None:
        raise DomainError("TRANSFER_NOT_ALLOWED", "Transfer is not ready for blockchain execution.")
    try:
        row = TransactionService().submit(
            contract_name="AssetRegistry",
            function_name="governedTransfer",
            args=[
                transfer.asset.token_id,
                Web3.to_checksum_address(transfer.sender.controller_address),
                Web3.to_checksum_address(transfer.recipient.controller_address),
            ],
            operation="ASSET_TRANSFER",
            idempotency_key=f"asset-transfer:{transfer.id}",
            actor_did=transfer.approved_by.identity.did,
            related_object_type="TransferRequest",
            related_object_id=transfer.id,
            correlation_id=correlation_id or None,
        )
        transfer.blockchain_transaction = row
        transfer.save(update_fields=["blockchain_transaction", "updated_at"])
        return str(row.id)
    except Exception as exc:
        transfer.state = TransferRequest.State.FAILED
        transfer.save(update_fields=["state", "updated_at"])
        create_alert(alert_type="TRANSACTION_REVERTED", severity=SecurityAlert.Severity.HIGH, title="Asset transfer submission failed", details={"transfer_id": str(transfer.id), "error": str(exc)[:500]}, correlation_id=correlation_id or None)
        raise
