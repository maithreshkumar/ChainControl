from django.db import models

from apps.common.models import UUIDTimeStampedModel


class ContractDeployment(UUIDTimeStampedModel):
    name = models.CharField(max_length=80)
    version = models.CharField(max_length=32)
    chain_id = models.PositiveBigIntegerField()
    address = models.CharField(max_length=42)
    abi = models.JSONField()
    deployment_tx_hash = models.CharField(max_length=66)
    deployment_block = models.PositiveBigIntegerField()
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["name", "version", "chain_id"], name="unique_contract_version_chain")]


class BlockchainTransaction(UUIDTimeStampedModel):
    class Status(models.TextChoices):
        CREATED = "CREATED", "Created"
        QUEUED = "QUEUED", "Queued"
        SUBMITTED = "SUBMITTED", "Submitted"
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        REVERTED = "REVERTED", "Reverted"
        FAILED = "FAILED", "Failed"
        DROPPED = "DROPPED", "Dropped"

    idempotency_key = models.CharField(max_length=160, unique=True)
    operation = models.CharField(max_length=80)
    actor_did = models.CharField(max_length=255, blank=True)
    contract_name = models.CharField(max_length=80)
    function_name = models.CharField(max_length=80)
    tx_hash = models.CharField(max_length=66, unique=True, null=True, blank=True)
    nonce = models.PositiveBigIntegerField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status, default=Status.CREATED)
    submitted_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    block_number = models.PositiveBigIntegerField(null=True, blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)
    error_code = models.CharField(max_length=80, blank=True)
    error_message = models.TextField(blank=True)
    related_object_type = models.CharField(max_length=80, blank=True)
    related_object_id = models.CharField(max_length=80, blank=True)
    correlation_id = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"]), models.Index(fields=["related_object_type", "related_object_id"])]


class BlockchainEvent(UUIDTimeStampedModel):
    tx_hash = models.CharField(max_length=66)
    log_index = models.PositiveIntegerField()
    block_number = models.PositiveBigIntegerField()
    contract_name = models.CharField(max_length=80)
    event_name = models.CharField(max_length=80)
    args = models.JSONField(default=dict)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tx_hash", "log_index"], name="unique_blockchain_log")]
        ordering = ["-block_number", "-log_index"]

