from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.assets.models import Asset, TransferRequest
from apps.identities.models import DecentralizedIdentity
from apps.audit.models import SecurityAlert
from apps.audit.services import create_alert, record_audit

from .client import get_web3
from .contracts import get_contract
from .models import BlockchainEvent, BlockchainTransaction


def _json_value(value):
    if isinstance(value, bytes):
        return "0x" + value.hex()
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    return value


@shared_task
def track_pending_transactions():
    web3 = get_web3()
    pending = BlockchainTransaction.objects.filter(status__in=[BlockchainTransaction.Status.SUBMITTED, BlockchainTransaction.Status.PENDING], tx_hash__isnull=False)
    for row in pending.iterator():
        try:
            receipt = web3.eth.get_transaction_receipt(row.tx_hash)
        except Exception:
            row.status = BlockchainTransaction.Status.PENDING
            row.save(update_fields=["status", "updated_at"])
            continue
        if web3.eth.block_number - receipt.blockNumber + 1 < settings.BLOCKCHAIN_CONFIRMATIONS:
            row.status = BlockchainTransaction.Status.PENDING
            row.save(update_fields=["status", "updated_at"])
            continue
        row.block_number = receipt.blockNumber
        row.confirmed_at = timezone.now()
        row.status = BlockchainTransaction.Status.CONFIRMED if receipt.status == 1 else BlockchainTransaction.Status.REVERTED
        row.save(update_fields=["block_number", "confirmed_at", "status", "updated_at"])
        if receipt.status != 1:
            if row.operation == "IDENTITY_REGISTER" and row.related_object_type == "DecentralizedIdentity":
                DecentralizedIdentity.objects.filter(id=row.related_object_id).update(
                    state=DecentralizedIdentity.State.REGISTRATION_FAILED,
                )
            create_alert(alert_type="TRANSACTION_REVERTED", severity=SecurityAlert.Severity.HIGH, title="Blockchain transaction reverted", details={"transaction_id": str(row.id), "tx_hash": row.tx_hash}, correlation_id=row.correlation_id)
            continue
        _index_known_events(row, receipt)


def _index_known_events(row, receipt):
    _, contract = get_contract(row.contract_name)
    for event_name in ("AssetMinted", "AssetTransferred", "AssetFrozen", "IdentityRegistered", "IdentityStateChanged", "IdentityKeyRotated"):
        event_factory = getattr(contract.events, event_name, None)
        if event_factory is None:
            continue
        try:
            logs = event_factory().process_receipt(receipt)
        except Exception:
            continue
        for log in logs:
            BlockchainEvent.objects.get_or_create(
                tx_hash=row.tx_hash,
                log_index=log["logIndex"],
                defaults={
                    "block_number": log["blockNumber"],
                    "contract_name": row.contract_name,
                    "event_name": event_name,
                    "args": _json_value(dict(log["args"])),
                },
            )
            if event_name == "AssetMinted" and row.related_object_type == "Asset":
                Asset.objects.filter(id=row.related_object_id).update(
                    token_id=int(log["args"]["tokenId"]),
                )
            if event_name == "AssetTransferred" and row.related_object_type == "TransferRequest":
                transfer = TransferRequest.objects.select_related("recipient").filter(id=row.related_object_id).first()
                if transfer:
                    Asset.objects.filter(id=transfer.asset_id).update(owner_projection=transfer.recipient)
                    transfer.state = TransferRequest.State.COMPLETED
                    transfer.save(update_fields=["state", "updated_at"])
            if event_name == "IdentityRegistered" and row.related_object_type == "DecentralizedIdentity":
                DecentralizedIdentity.objects.filter(id=row.related_object_id).update(
                    state=DecentralizedIdentity.State.ACTIVE,
                    registration_tx_hash=row.tx_hash,
                )
        if logs:
            record_audit(action=f"blockchain.{event_name}", object_type=row.related_object_type or row.contract_name, object_id=row.related_object_id, correlation_id=row.correlation_id, details={"tx_hash": row.tx_hash})


@shared_task
def reconcile_asset_ownership():
    _, contract = get_contract("AssetRegistry")
    for asset in Asset.objects.filter(token_id__isnull=False).select_related("owner_projection"):
        try:
            owner = contract.functions.ownerOf(asset.token_id).call()
        except Exception:
            continue
        projected_controller = asset.owner_projection.controller_address if asset.owner_projection else None
        if projected_controller is None or owner.lower() != projected_controller.lower():
            if projected_controller is not None:
                create_alert(
                    alert_type="BLOCKCHAIN_DB_MISMATCH",
                    severity=SecurityAlert.Severity.CRITICAL,
                    title="Asset ownership projection differs from blockchain",
                    details={"asset_id": str(asset.id), "token_id": asset.token_id, "projected": projected_controller, "on_chain": owner},
                )
            authoritative_identity = DecentralizedIdentity.objects.filter(controller_address__iexact=owner).first()
            if authoritative_identity:
                previous = asset.owner_projection_id
                asset.owner_projection = authoritative_identity
                asset.save(update_fields=["owner_projection", "updated_at"])
                record_audit(
                    action="reconciliation.asset_owner_repaired",
                    object_type="Asset",
                    object_id=asset.id,
                    details={"previous_identity_id": str(previous), "authoritative_identity_id": str(authoritative_identity.id), "token_id": asset.token_id},
                )
