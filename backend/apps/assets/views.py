from django.db import models, transaction
from rest_framework import status, viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone

from apps.audit.models import SecurityAlert
from apps.audit.services import create_alert, record_audit
from apps.common.errors import DomainError
from apps.common.permissions import HasPermissionCode
from apps.identities.permissions import RequiresDIDProof
from apps.blockchain.models import BlockchainEvent, BlockchainTransaction

from .models import Asset, AssetVersion, IntegrityCheck, TransferRequest
from .serializers import AssetSerializer, TransferSerializer
from .storage import retrieve_and_verify, store_encrypted


class AssetViewSet(viewsets.ModelViewSet):
    serializer_class = AssetSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        if user.has_platform_permission("asset.view_all"):
            return Asset.objects.select_related("owner_projection", "department").prefetch_related("versions").order_by("-created_at")
        visibility = models.Q(created_by=user) | models.Q(owner_projection__user=user)
        if user.department_id and user.has_platform_permission("asset.view", department_id=user.department_id):
            visibility |= models.Q(department_id=user.department_id)
        return Asset.objects.filter(visibility).distinct().select_related("owner_projection", "department").prefetch_related("versions").order_by("-created_at")

    def get_permissions(self):
        if self.action == "create":
            self.permission_code = "asset.mint"
            self.did_proof_purpose = "ASSET_MINT"
            return [HasPermissionCode(), RequiresDIDProof()]
        if self.action == "activate":
            self.permission_code = "asset.activate"
            self.did_proof_purpose = "ASSET_ACTIVATE"
            return [HasPermissionCode(), RequiresDIDProof()]
        if self.action == "refresh_blockchain":
            self.permission_code = "asset.view"
            return [HasPermissionCode()]
        return super().get_permissions()

    @action(detail=False, methods=["post"], url_path="refresh-blockchain")
    def refresh_blockchain(self, request):
        from apps.blockchain.tasks import track_pending_transactions
        track_pending_transactions.delay()
        record_audit(
            action="blockchain.refresh.requested",
            object_type="AssetRegistry",
            actor=request.user,
            correlation_id=getattr(request, "correlation_id", None),
        )
        return Response(
            {"status": "QUEUED", "message": "Blockchain receipt refresh has been queued."},
            status=status.HTTP_202_ACCEPTED,
        )

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        asset = serializer.save(
            created_by=request.user,
            owner_projection=request.user.identity,
            department=request.user.department,
            asset_type=Asset.AssetType.DIGITAL_ASSET if serializer.validated_data["kind"] == Asset.Kind.DIGITAL else Asset.AssetType.UNIQUE_PHYSICAL_ASSET,
            state=Asset.State.PROCESSING,
        )
        if asset.kind == Asset.Kind.DIGITAL:
            uploaded = request.FILES.get("file")
            if uploaded is None:
                raise DomainError("ASSET_FILE_REQUIRED", "A digital asset requires a file.")
            stored = store_encrypted(
                asset_id=asset.id,
                version=1,
                plaintext=uploaded.read(),
                mime_type=uploaded.content_type or "application/octet-stream",
                metadata={"asset_id": str(asset.id), "name": asset.name, "kind": asset.kind, "classification": asset.classification},
            )
            AssetVersion.objects.create(asset=asset, version=1, **stored)
        else:
            if not asset.serial_number:
                raise DomainError("SERIAL_NUMBER_REQUIRED", "A physical asset requires a serial number.")
            import hashlib
            import json
            metadata = {"asset_id": str(asset.id), "name": asset.name, "serial_number": asset.serial_number}
            digest = hashlib.sha256(json.dumps(metadata, sort_keys=True).encode()).hexdigest()
            AssetVersion.objects.create(asset=asset, version=1, content_hash=digest, metadata_hash=digest)
        asset.state = Asset.State.BLOCKCHAIN_PENDING
        asset.save(update_fields=["state", "updated_at"])
        from .tasks import submit_asset_mint
        transaction.on_commit(lambda: submit_asset_mint.delay(str(asset.id), str(getattr(request, "correlation_id", ""))))
        record_audit(action="asset.registration.requested", object_type="Asset", object_id=asset.id, actor=request.user, correlation_id=getattr(request, "correlation_id", None))
        return Response(self.get_serializer(asset).data, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def activate(self, request, pk=None):
        asset = self.get_object()
        if asset.state != Asset.State.BLOCKCHAIN_PENDING:
            raise DomainError("ASSET_NOT_PENDING", "Only a blockchain-pending asset can be activated.", status_code=409)
        if asset.created_by_id == request.user.id:
            raise DomainError("SELF_VALIDATION_FORBIDDEN", "Validators cannot approve an asset they registered.", status_code=403)

        confirmed_tx = BlockchainTransaction.objects.filter(
            operation="ASSET_MINT",
            related_object_type="Asset",
            related_object_id=str(asset.id),
            status=BlockchainTransaction.Status.CONFIRMED,
            tx_hash__isnull=False,
        ).order_by("-confirmed_at").first()
        if confirmed_tx is None:
            raise DomainError("ASSET_MINT_NOT_CONFIRMED", "The mint transaction is not confirmed yet. Try verification again shortly.", status_code=409)

        mint_event = BlockchainEvent.objects.filter(tx_hash=confirmed_tx.tx_hash, event_name="AssetMinted").first()
        if mint_event is None:
            raise DomainError("ASSET_MINT_EVENT_MISSING", "The confirmed mint event has not been indexed yet.", status_code=409)

        if asset.kind == Asset.Kind.DIGITAL:
            version = asset.versions.order_by("-version").first()
            if version is None:
                raise DomainError("ASSET_NOT_VERIFIABLE", "This digital asset has no stored version.", status_code=409)
            try:
                retrieve_and_verify(version)
                IntegrityCheck.objects.create(
                    asset_version=version,
                    checked_by=request.user,
                    expected_hash=version.content_hash,
                    calculated_hash=version.content_hash,
                    passed=True,
                )
            except DomainError as exc:
                IntegrityCheck.objects.create(
                    asset_version=version,
                    checked_by=request.user,
                    expected_hash=version.content_hash,
                    passed=False,
                    error_code=exc.code,
                )
                create_alert(
                    alert_type="FILE_INTEGRITY_FAILURE",
                    severity=SecurityAlert.Severity.CRITICAL,
                    title="Asset activation blocked by integrity verification",
                    details={"asset_id": str(asset.id)},
                    correlation_id=getattr(request, "correlation_id", None),
                )
                raise

        event_token_id = int(mint_event.args["tokenId"])
        if asset.token_id is not None and asset.token_id != event_token_id:
            raise DomainError("ASSET_TOKEN_MISMATCH", "The indexed token does not match the asset projection.", status_code=409)
        asset.token_id = event_token_id
        asset.state = Asset.State.ACTIVE
        asset.save(update_fields=["token_id", "state", "updated_at"])
        record_audit(
            action="asset.registration.activated",
            object_type="Asset",
            object_id=asset.id,
            actor=request.user,
            correlation_id=getattr(request, "correlation_id", None),
            details={"tx_hash": confirmed_tx.tx_hash, "token_id": event_token_id},
        )
        return Response(self.get_serializer(asset).data)

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        asset = self.get_object()
        version = asset.versions.order_by("-version").first()
        if not version or asset.kind != Asset.Kind.DIGITAL:
            raise DomainError("ASSET_NOT_VERIFIABLE", "This asset has no digital content to verify.")
        try:
            retrieve_and_verify(version)
            check = IntegrityCheck.objects.create(asset_version=version, checked_by=request.user, expected_hash=version.content_hash, calculated_hash=version.content_hash, passed=True)
        except DomainError as exc:
            check = IntegrityCheck.objects.create(asset_version=version, checked_by=request.user, expected_hash=version.content_hash, passed=False, error_code=exc.code)
            create_alert(alert_type="FILE_INTEGRITY_FAILURE", severity=SecurityAlert.Severity.CRITICAL, title="Asset integrity verification failed", details={"asset_id": str(asset.id)}, correlation_id=getattr(request, "correlation_id", None))
            raise
        return Response({"integrity_check_id": check.id, "passed": True, "hash": version.content_hash})


class TransferViewSet(viewsets.ModelViewSet):
    serializer_class = TransferSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        if user.has_platform_permission("transfer.view_all"):
            return TransferRequest.objects.all()
        return TransferRequest.objects.filter(models.Q(sender__user=user) | models.Q(recipient__user=user))

    def get_permissions(self):
        permission_map = {
            "create": "asset.transfer",
            "accept": "asset.transfer",
            "reject": "asset.transfer",
            "cancel": "asset.transfer",
            "approve": "transfer.approve",
        }
        if self.action in permission_map:
            self.permission_code = permission_map[self.action]
            self.did_proof_purpose = "ASSET_TRANSFER"
            return [HasPermissionCode(), RequiresDIDProof()]
        return super().get_permissions()

    def perform_create(self, serializer):
        identity = self.request.user.identity
        asset = serializer.validated_data["asset"]
        if asset.owner_projection_id != identity.id or asset.state != Asset.State.ACTIVE:
            raise DomainError("TRANSFER_NOT_ALLOWED", "Only the active projected owner can request this transfer.", status_code=403)
        if serializer.validated_data["recipient"].id == identity.id:
            raise DomainError("TRANSFER_NOT_ALLOWED", "An asset cannot be transferred to the same identity.")
        transfer = serializer.save(sender=identity)
        record_audit(action="asset.transfer.requested", object_type="TransferRequest", object_id=transfer.id, actor=self.request.user, correlation_id=getattr(self.request, "correlation_id", None), details={"asset_id": str(asset.id), "recipient_did": transfer.recipient.did})

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        transfer = self.get_object()
        if transfer.recipient.user_id != request.user.id or transfer.state != TransferRequest.State.PENDING_RECIPIENT:
            raise DomainError("TRANSFER_NOT_ALLOWED", "This transfer cannot be accepted by the current user.", status_code=403)
        transfer.state = TransferRequest.State.PENDING_APPROVAL
        transfer.recipient_acted_at = timezone.now()
        transfer.save(update_fields=["state", "recipient_acted_at", "updated_at"])
        record_audit(action="asset.transfer.accepted", object_type="TransferRequest", object_id=transfer.id, actor=request.user, correlation_id=getattr(request, "correlation_id", None))
        return Response(self.get_serializer(transfer).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        transfer = self.get_object()
        if transfer.recipient.user_id != request.user.id or transfer.state != TransferRequest.State.PENDING_RECIPIENT:
            raise DomainError("TRANSFER_NOT_ALLOWED", "This transfer cannot be rejected by the current user.", status_code=403)
        transfer.state = TransferRequest.State.REJECTED
        transfer.recipient_acted_at = timezone.now()
        transfer.save(update_fields=["state", "recipient_acted_at", "updated_at"])
        record_audit(action="asset.transfer.rejected", object_type="TransferRequest", object_id=transfer.id, actor=request.user, correlation_id=getattr(request, "correlation_id", None))
        return Response(self.get_serializer(transfer).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        transfer = self.get_object()
        if transfer.sender.user_id != request.user.id or transfer.state not in {TransferRequest.State.PENDING_RECIPIENT, TransferRequest.State.PENDING_APPROVAL}:
            raise DomainError("TRANSFER_NOT_ALLOWED", "Only the sender can cancel a transfer before approval.", status_code=403)
        transfer.state = TransferRequest.State.CANCELLED
        transfer.save(update_fields=["state", "updated_at"])
        record_audit(action="asset.transfer.cancelled", object_type="TransferRequest", object_id=transfer.id, actor=request.user, correlation_id=getattr(request, "correlation_id", None))
        return Response(self.get_serializer(transfer).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        transfer = self.get_object()
        if transfer.state != TransferRequest.State.PENDING_APPROVAL:
            raise DomainError("TRANSFER_NOT_ALLOWED", "Transfer is not waiting for approval.", status_code=409)
        if request.user.id in {transfer.sender.user_id, transfer.recipient.user_id}:
            raise DomainError("SELF_APPROVAL_FORBIDDEN", "Sender and recipient cannot approve their own transfer.", status_code=403)
        if transfer.asset.department_id and not request.user.has_platform_permission("transfer.approve", department_id=transfer.asset.department_id):
            raise DomainError("ROLE_NOT_AUTHORIZED", "Approver is outside the asset scope.", status_code=403)
        transfer.state = TransferRequest.State.BLOCKCHAIN_PENDING
        transfer.approved_by = request.user
        transfer.approved_at = timezone.now()
        transfer.save(update_fields=["state", "approved_by", "approved_at", "updated_at"])
        record_audit(action="asset.transfer.approved", object_type="TransferRequest", object_id=transfer.id, actor=request.user, correlation_id=getattr(request, "correlation_id", None), details={"asset_id": str(transfer.asset_id)})
        from .tasks import submit_asset_transfer
        submit_asset_transfer.delay(str(transfer.id), str(getattr(request, "correlation_id", "")))
        return Response(self.get_serializer(transfer).data, status=status.HTTP_202_ACCEPTED)
