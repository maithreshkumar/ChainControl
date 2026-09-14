from django.urls import path

from .views import AuditListView, SecurityAlertListView

urlpatterns = [
    path("audit/", AuditListView.as_view(), name="audit-list"),
    path("security-alerts/", SecurityAlertListView.as_view(), name="security-alert-list"),
]

