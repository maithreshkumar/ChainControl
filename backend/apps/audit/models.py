from django.conf import settings
from django.db import models

from apps.common.models import UUIDTimeStampedModel


class AuditEvent(UUIDTimeStampedModel):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="audit_events")
    action = models.CharField(max_length=100)
    object_type = models.CharField(max_length=80)
    object_id = models.CharField(max_length=80, blank=True)
    outcome = models.CharField(max_length=20, default="SUCCESS")
    correlation_id = models.UUIDField(null=True, blank=True)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["action", "created_at"]), models.Index(fields=["object_type", "object_id"])]


class SecurityAlert(UUIDTimeStampedModel):
    class Severity(models.TextChoices):
        INFO = "INFO", "Info"
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        CRITICAL = "CRITICAL", "Critical"

    alert_type = models.CharField(max_length=80)
    severity = models.CharField(max_length=10, choices=Severity)
    title = models.CharField(max_length=160)
    details = models.JSONField(default=dict)
    correlation_id = models.UUIDField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

