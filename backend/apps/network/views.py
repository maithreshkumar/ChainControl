from django.db import transaction
from django.db.models import Count, Max
from django.utils import timezone
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.errors import DomainError
from apps.audit.services import record_audit

from .authentication import NodeCredentialAuthentication
from .models import BlockchainNode, NodePeerSnapshot
from .permissions import IsAuthenticatedNode, IsDjangoSuperuser
from .serializers import BlockchainNodeSerializer, NodeEnrollmentSerializer, NodeHeartbeatSerializer
from .services import NetworkAdmissionError, bootstrap_configuration_for, create_enrollment, current_validator_set, network_configuration
from .throttles import NodeEnrollmentThrottle, NodeHeartbeatThrottle, NodeStatusThrottle


def admission_error(exc, *, status_code=409):
    return DomainError("NETWORK_ADMISSION_FAILED", str(exc), status_code=status_code)


class NodeEnrollmentView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [NodeEnrollmentThrottle]

    def post(self, request):
        serializer = NodeEnrollmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            node, secret = create_enrollment(dict(serializer.validated_data))
        except NetworkAdmissionError as exc:
            raise admission_error(exc, status_code=403) from exc
        return Response(
            {
                "node_uuid": node.node_uuid,
                "status": node.status,
                "node_credential": f"{node.node_uuid}.{secret}",
                "message": "Enrollment is pending Django superuser approval.",
            },
            status=status.HTTP_202_ACCEPTED,
        )


class NodeSelfMixin:
    authentication_classes = [NodeCredentialAuthentication]
    permission_classes = [IsAuthenticatedNode]

    def node(self, request, node_uuid):
        node = request.auth
        if str(node.node_uuid) != str(node_uuid):
            raise DomainError("NODE_CREDENTIAL_SCOPE_INVALID", "This credential belongs to a different node.", status_code=403)
        return node


class NodeEnrollmentStatusView(NodeSelfMixin, APIView):
    throttle_classes = [NodeStatusThrottle]

    def get(self, request, node_uuid):
        node = self.node(request, node_uuid)
        return Response(
            {
                "node_uuid": node.node_uuid,
                "node_name": node.node_name,
                "status": node.status,
                "node_type": node.node_type,
                "is_validator": node.is_validator,
                "approved_at": node.approved_at,
                "rejection_reason": node.rejection_reason if node.status == node.Status.REJECTED else "",
                "revocation_reason": node.revocation_reason if node.status == node.Status.REVOKED else "",
                "configuration_ready": node.is_admitted and bool(network_configuration().genesis_hash),
            }
        )


class NodeConfigurationView(NodeSelfMixin, APIView):
    throttle_classes = [NodeStatusThrottle]

    def get(self, request, node_uuid):
        node = self.node(request, node_uuid)
        try:
            return Response(bootstrap_configuration_for(node))
        except NetworkAdmissionError as exc:
            raise admission_error(exc, status_code=403) from exc


class NodeHeartbeatView(NodeSelfMixin, APIView):
    throttle_classes = [NodeHeartbeatThrottle]

    @transaction.atomic
    def post(self, request, node_uuid):
        node = self.node(request, node_uuid)
        if not node.is_admitted:
            raise DomainError("NODE_NOT_ADMITTED", "This node is not admitted to the network.", status_code=403)
        serializer = NodeHeartbeatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        now = timezone.now()
        previous_status = node.status
        node.latest_block = values["latest_block"]
        node.network_latest_block = values["network_latest_block"]
        node.peer_count = values["peer_count"]
        node.sync_percentage = values["sync_percentage"]
        node.sync_state = values["sync_state"]
        node.software_version = values["software_version"]
        node.last_seen = now
        if node.joined_at is None:
            node.joined_at = now
        node.status = {
            "CONNECTING": node.Status.CONNECTING,
            "SYNCING": node.Status.SYNCING,
            "ONLINE": node.Status.ONLINE,
            "DEGRADED": node.Status.DEGRADED,
        }[values["sync_state"]]
        node.save(update_fields=[
            "latest_block", "network_latest_block", "peer_count", "sync_percentage", "sync_state",
            "software_version", "last_seen", "joined_at", "status", "updated_at",
        ])
        if node.status == node.Status.ONLINE and previous_status != node.Status.ONLINE:
            record_audit(
                action="NODE_SYNCED",
                object_type="BlockchainNode",
                object_id=node.id,
                actor=node.owner,
                details={"latest_block": node.latest_block, "network_latest_block": node.network_latest_block},
            )
        peer_enodes = values.get("peer_enodes", [])
        NodePeerSnapshot.objects.filter(reporter=node).exclude(peer_enode__in=peer_enodes).delete()
        for enode in peer_enodes:
            NodePeerSnapshot.objects.update_or_create(reporter=node, peer_enode=enode, defaults={"observed_at": now})
        configuration = network_configuration()
        return Response({"accepted": True, "status": node.status, "permissioning_revision": configuration.permissioning_revision})


class NetworkSummaryView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsDjangoSuperuser]

    def get(self, request):
        counts = BlockchainNode.objects.values("status", "node_type").annotate(total=Count("id"))
        nodes = BlockchainNodeSerializer(BlockchainNode.objects.select_related("owner").all(), many=True).data
        latest = BlockchainNode.objects.aggregate(value=Max("latest_block"))["value"]
        try:
            validators = current_validator_set()
            consensus = "HEALTHY" if validators else "UNAVAILABLE"
        except NetworkAdmissionError:
            validators = []
            consensus = "UNAVAILABLE"
        enode_to_uuid = {node.enode.lower(): str(node.node_uuid) for node in BlockchainNode.objects.all()}
        edges = []
        for snapshot in NodePeerSnapshot.objects.select_related("reporter"):
            peer_uuid = enode_to_uuid.get(snapshot.peer_enode.lower())
            if peer_uuid:
                edges.append({"source": str(snapshot.reporter.node_uuid), "target": peer_uuid, "observed_at": snapshot.observed_at})
        return Response(
            {
                "counts": list(counts),
                "latest_block": latest,
                "validator_count": len(validators),
                "validator_addresses": validators,
                "consensus": consensus,
                "nodes": nodes,
                "topology_edges": edges,
            }
        )
