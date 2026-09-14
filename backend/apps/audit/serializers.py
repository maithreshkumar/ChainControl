from rest_framework import serializers

from .models import AuditEvent, SecurityAlert


class AuditEventSerializer(serializers.ModelSerializer):
    actor = serializers.CharField(source="actor.username", allow_null=True)

    class Meta:
        model = AuditEvent
        fields = "__all__"


class SecurityAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = SecurityAlert
        fields = "__all__"

