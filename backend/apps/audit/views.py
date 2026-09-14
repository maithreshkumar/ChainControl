from rest_framework import generics

from apps.common.permissions import HasPermissionCode

from .models import AuditEvent, SecurityAlert
from .serializers import AuditEventSerializer, SecurityAlertSerializer


class AuditListView(generics.ListAPIView):
    queryset = AuditEvent.objects.select_related("actor").all()
    serializer_class = AuditEventSerializer
    permission_classes = [HasPermissionCode]
    permission_code = "audit.view"


class SecurityAlertListView(generics.ListAPIView):
    queryset = SecurityAlert.objects.all()
    serializer_class = SecurityAlertSerializer
    permission_classes = [HasPermissionCode]
    permission_code = "security.view"

