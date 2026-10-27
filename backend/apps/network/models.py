import uuid

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.db import models
from django.utils import timezone

from apps.common.models import UUIDTimeStampedModel


class EnrollmentToken(UUIDTimeStampedModel):
    label = models.CharField(max_length=120)
    token_digest = models.CharField(max_length=255, unique=True)
    intended_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="network_enrollment_tokens",
    )
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_network_enrollment_tokens",
    )

    class Meta:
        ordering = ["-created_at"]

    @property
    def usable(self):
        return self.used_at is None and self.expires_at > timezone.now()

    def matches(self, plaintext):
        return self.usable and check_password(plaintext, self.token_digest)

    def __str__(self):
        return f"{self.label} ({'available' if self.usable else 'closed'})"


class NetworkConfiguration(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    network_name = models.CharField(max_length=80, default="ChainControl Network")
    chain_id = models.PositiveBigIntegerField(default=1337)
    genesis_hash = models.CharField(max_length=64, blank=True)
    genesis_json = models.JSONField(null=True, blank=True)
    genesis_text = models.TextField(blank=True)
    permissioning_revision = models.PositiveBigIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="network_configuration_updates",
    )

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.network_name} · chain {self.chain_id} · revision {self.permissioning_revision}"


class BlockchainNode(UUIDTimeStampedModel):
    class NodeType(models.TextChoices):
        FULL_NODE = "FULL_NODE", "Full / replica node"
        VALIDATOR = "VALIDATOR", "QBFT validator"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending approval"
        APPROVED = "APPROVED", "Approved"
        CONNECTING = "CONNECTING", "Connecting"
        SYNCING = "SYNCING", "Synchronizing"
        ONLINE = "ONLINE", "Online"
        DEGRADED = "DEGRADED", "Degraded"
        OFFLINE = "OFFLINE", "Offline"
        REJECTED = "REJECTED", "Rejected"
        REVOKED = "REVOKED", "Revoked"

    node_uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    node_name = models.CharField(max_length=120)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="blockchain_nodes",
    )
    enode = models.CharField(max_length=255, unique=True)
    node_public_key = models.CharField(max_length=128, unique=True)
    node_address = models.CharField(max_length=42, unique=True)
    host_or_overlay_address = models.GenericIPAddressField(protocol="both", unpack_ipv4=True)
    p2p_port = models.PositiveIntegerField(default=30303)
    rpc_port = models.PositiveIntegerField(default=8545)
    ws_port = models.PositiveIntegerField(default=8546)
    node_type = models.CharField(max_length=16, choices=NodeType, default=NodeType.FULL_NODE)
    status = models.CharField(max_length=16, choices=Status, default=Status.PENDING)
    is_validator = models.BooleanField(default=False)
    requested_validator = models.BooleanField(default=False)
    software_version = models.CharField(max_length=32, blank=True)
    latest_block = models.PositiveBigIntegerField(null=True, blank=True)
    network_latest_block = models.PositiveBigIntegerField(null=True, blank=True)
    sync_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    peer_count = models.PositiveIntegerField(null=True, blank=True)
    sync_state = models.CharField(max_length=32, blank=True)
    requested_at = models.DateTimeField(default=timezone.now)
    approved_at = models.DateTimeField(null=True, blank=True)
    joined_at = models.DateTimeField(null=True, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="approved_blockchain_nodes",
    )
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="rejected_blockchain_nodes",
    )
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="revoked_blockchain_nodes",
    )
    rejection_reason = models.TextField(blank=True)
    revocation_reason = models.TextField(blank=True)
    configuration_error = models.TextField(blank=True)
    enrollment_token = models.ForeignKey(
        EnrollmentToken,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="nodes",
    )

    class Meta:
        ordering = ["node_name", "node_uuid"]
        indexes = [models.Index(fields=["status", "last_seen"]), models.Index(fields=["node_type", "is_validator"])]

    @property
    def is_admitted(self):
        return self.status not in {self.Status.PENDING, self.Status.REJECTED, self.Status.REVOKED}

    def __str__(self):
        return f"{self.node_name} · {self.node_type} · {self.status}"


class NodeCredential(UUIDTimeStampedModel):
    node = models.OneToOneField(BlockchainNode, on_delete=models.CASCADE, related_name="credential")
    secret_digest = models.CharField(max_length=255)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    def matches(self, plaintext):
        return self.revoked_at is None and check_password(plaintext, self.secret_digest)

    def __str__(self):
        return f"Credential for {self.node.node_name}"


class NodePeerSnapshot(UUIDTimeStampedModel):
    reporter = models.ForeignKey(BlockchainNode, on_delete=models.CASCADE, related_name="peer_snapshots")
    peer_enode = models.CharField(max_length=255)
    observed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-observed_at"]
        constraints = [models.UniqueConstraint(fields=["reporter", "peer_enode"], name="unique_reported_peer")]


class ValidatorGovernanceOperation(UUIDTimeStampedModel):
    class Action(models.TextChoices):
        ADD = "ADD", "Promote to validator"
        REMOVE = "REMOVE", "Remove validator"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        IN_PROGRESS = "IN_PROGRESS", "Voting in progress"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    node = models.ForeignKey(BlockchainNode, on_delete=models.PROTECT, related_name="validator_operations")
    action = models.CharField(max_length=8, choices=Action)
    status = models.CharField(max_length=16, choices=Status, default=Status.PENDING)
    candidate_address = models.CharField(max_length=42)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="validator_governance_requests",
    )
    votes = models.JSONField(default=list, blank=True)
    validator_set_before = models.JSONField(default=list, blank=True)
    validator_set_after = models.JSONField(default=list, blank=True)
    error_message = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "action"])]

    def __str__(self):
        return f"{self.get_action_display()} · {self.node.node_name} · {self.status}"
