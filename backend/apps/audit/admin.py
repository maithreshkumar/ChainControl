from django.contrib import admin

from apps.common.admin import ReadOnlyAdmin

from .models import AuditEvent, SecurityAlert


@admin.register(AuditEvent)
class AuditEventAdmin(ReadOnlyAdmin):
    list_display = ("created_at", "action", "actor", "object_type", "object_id", "outcome")
    search_fields = ("action", "actor__username", "object_type", "object_id", "correlation_id")
    list_filter = ("outcome", "object_type", "action")


@admin.register(SecurityAlert)
class SecurityAlertAdmin(ReadOnlyAdmin):
    list_display = ("created_at", "severity", "alert_type", "title", "acknowledged_at")
    search_fields = ("alert_type", "title", "correlation_id")
    list_filter = ("severity", "alert_type")
