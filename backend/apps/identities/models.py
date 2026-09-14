from django.conf import settings
from django.db import models

from apps.common.models import UUIDTimeStampedModel


class DecentralizedIdentity(UUIDTimeStampedModel):
    class State(models.TextChoices):
        INVITED = "INVITED", "Invited"
        VALIDATION_PENDING = "VALIDATION_PENDING", "Validation pending"
        BLOCKCHAIN_PENDING = "BLOCKCHAIN_PENDING", "Blockchain pending"
        ACTIVE = "ACTIVE", "Active"
        SUSPENDED = "SUSPENDED", "Suspended"
        REVOKED = "REVOKED", "Revoked"
        REGISTRATION_FAILED = "REGISTRATION_FAILED", "Registration failed"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="identity")
    did = models.CharField(max_length=255, unique=True)
    controller_address = models.CharField(max_length=42, unique=True)
    state = models.CharField(max_length=24, choices=State, default=State.INVITED)
    key_version = models.PositiveIntegerField(default=1)
    registration_tx_hash = models.CharField(max_length=66, blank=True)

    def __str__(self):
        return self.did


class IdentityKey(UUIDTimeStampedModel):
    identity = models.ForeignKey(DecentralizedIdentity, on_delete=models.PROTECT, related_name="keys")
    version = models.PositiveIntegerField()
    controller_address = models.CharField(max_length=42)
    public_key = models.TextField(blank=True)
    active_from = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    rotation_tx_hash = models.CharField(max_length=66, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["identity", "version"], name="unique_identity_key_version")]


class AuthenticationChallenge(UUIDTimeStampedModel):
    identity = models.ForeignKey(DecentralizedIdentity, on_delete=models.CASCADE, related_name="challenges")
    purpose = models.CharField(max_length=80)
    nonce_digest = models.CharField(max_length=64, unique=True)
    message = models.TextField()
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    request_correlation_id = models.UUIDField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["identity", "purpose", "expires_at"])]
