from django.conf import settings
from django.db import models

from apps.common.models import UUIDTimeStampedModel


class Asset(UUIDTimeStampedModel):
    class AssetType(models.TextChoices):
        UNIQUE_PHYSICAL_ASSET = "UNIQUE_PHYSICAL_ASSET", "Unique physical asset"
        DIGITAL_ASSET = "DIGITAL_ASSET", "Digital asset"

    class Kind(models.TextChoices):
        DIGITAL = "DIGITAL", "Digital"
        PHYSICAL = "PHYSICAL", "Physical"

    class State(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PROCESSING = "PROCESSING", "Processing"
        BLOCKCHAIN_PENDING = "BLOCKCHAIN_PENDING", "Blockchain pending"
        ACTIVE = "ACTIVE", "Active"
        FROZEN = "FROZEN", "Frozen"
        ARCHIVED = "ARCHIVED", "Archived"
        REVOKED = "REVOKED", "Revoked"
        REGISTRATION_FAILED = "REGISTRATION_FAILED", "Registration failed"

    name = models.CharField(max_length=180)
    kind = models.CharField(max_length=16, choices=Kind)
    asset_type = models.CharField(max_length=32, choices=AssetType)
    classification = models.PositiveSmallIntegerField(default=10)
    department = models.ForeignKey("accounts.Department", null=True, on_delete=models.PROTECT, related_name="assets")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_assets")
    owner_projection = models.ForeignKey("identities.DecentralizedIdentity", null=True, blank=True, on_delete=models.PROTECT, related_name="owned_assets")
    state = models.CharField(max_length=24, choices=State, default=State.DRAFT)
    token_id = models.PositiveBigIntegerField(null=True, blank=True, unique=True)
    serial_number = models.CharField(max_length=120, blank=True, unique=True, null=True)
    custody_identifier = models.CharField(max_length=180, blank=True)

    class Meta:
        indexes = [models.Index(fields=["state", "department"]), models.Index(fields=["asset_type", "state"], name="assets_asse_asset_t_2ad6b6_idx")]

    def save(self, *args, **kwargs):
        if not self.asset_type:
            self.asset_type = self.AssetType.DIGITAL_ASSET if self.kind == self.Kind.DIGITAL else self.AssetType.UNIQUE_PHYSICAL_ASSET
        super().save(*args, **kwargs)


class AssetVersion(UUIDTimeStampedModel):
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name="versions")
    version = models.PositiveIntegerField()
    content_hash = models.CharField(max_length=64)
    metadata_hash = models.CharField(max_length=64)
    object_key = models.CharField(max_length=512, blank=True)
    content_nonce = models.CharField(max_length=32, blank=True)
    wrapped_key = models.TextField(blank=True)
    wrap_nonce = models.CharField(max_length=32, blank=True)
    size = models.PositiveBigIntegerField(default=0)
    mime_type = models.CharField(max_length=160, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["asset", "version"], name="unique_asset_version"),
            models.UniqueConstraint(fields=["asset", "content_hash"], name="unique_asset_content_hash"),
        ]


class IntegrityCheck(UUIDTimeStampedModel):
    asset_version = models.ForeignKey(AssetVersion, on_delete=models.PROTECT, related_name="integrity_checks")
    checked_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    expected_hash = models.CharField(max_length=64)
    calculated_hash = models.CharField(max_length=64, blank=True)
    passed = models.BooleanField(default=False)
    error_code = models.CharField(max_length=80, blank=True)


class TransferRequest(UUIDTimeStampedModel):
    class State(models.TextChoices):
        PENDING_RECIPIENT = "PENDING_RECIPIENT", "Pending recipient"
        PENDING_APPROVAL = "PENDING_APPROVAL", "Pending approval"
        BLOCKCHAIN_PENDING = "BLOCKCHAIN_PENDING", "Blockchain pending"
        COMPLETED = "COMPLETED", "Completed"
        REJECTED = "REJECTED", "Rejected"
        FAILED = "FAILED", "Failed"
        CANCELLED = "CANCELLED", "Cancelled"

    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name="transfers")
    sender = models.ForeignKey("identities.DecentralizedIdentity", on_delete=models.PROTECT, related_name="outgoing_transfers")
    recipient = models.ForeignKey("identities.DecentralizedIdentity", on_delete=models.PROTECT, related_name="incoming_transfers")
    state = models.CharField(max_length=24, choices=State, default=State.PENDING_RECIPIENT)
    recipient_acted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="approved_transfers")
    approved_at = models.DateTimeField(null=True, blank=True)
    blockchain_transaction = models.ForeignKey("blockchain.BlockchainTransaction", null=True, blank=True, on_delete=models.PROTECT)
