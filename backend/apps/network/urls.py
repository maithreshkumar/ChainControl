from django.urls import path

from .views import NodeConfigurationView, NodeEnrollmentStatusView, NodeEnrollmentView, NodeHeartbeatView, NetworkSummaryView


urlpatterns = [
    path("network/enrollment/", NodeEnrollmentView.as_view(), name="network-enrollment"),
    path("network/enrollment/status/<uuid:node_uuid>/", NodeEnrollmentStatusView.as_view(), name="network-enrollment-status"),
    path("network/nodes/<uuid:node_uuid>/configuration/", NodeConfigurationView.as_view(), name="network-node-configuration"),
    path("network/nodes/<uuid:node_uuid>/heartbeat/", NodeHeartbeatView.as_view(), name="network-node-heartbeat"),
    path("network/summary/", NetworkSummaryView.as_view(), name="network-summary"),
]
