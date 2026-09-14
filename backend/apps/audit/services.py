from .models import AuditEvent, SecurityAlert


def record_audit(*, action, object_type, actor=None, object_id="", outcome="SUCCESS", correlation_id=None, details=None):
    return AuditEvent.objects.create(
        actor=actor,
        action=action,
        object_type=object_type,
        object_id=str(object_id),
        outcome=outcome,
        correlation_id=correlation_id,
        details=details or {},
    )


def create_alert(*, alert_type, severity, title, details=None, correlation_id=None):
    return SecurityAlert.objects.create(
        alert_type=alert_type,
        severity=severity,
        title=title,
        details=details or {},
        correlation_id=correlation_id,
    )

