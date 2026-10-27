from rest_framework import serializers

from .models import BlockchainNode, NodePeerSnapshot
from .validation import address_from_public_key, normalize_address, normalize_public_key, parse_enode, validate_private_overlay_ip


class NodeEnrollmentSerializer(serializers.Serializer):
    enrollment_code = serializers.CharField(min_length=16, max_length=256, write_only=True)
    node_uuid = serializers.UUIDField()
    node_name = serializers.CharField(min_length=3, max_length=120)
    enode = serializers.CharField(max_length=255)
    node_public_key = serializers.CharField(max_length=130)
    node_address = serializers.CharField(max_length=42)
    host_or_overlay_address = serializers.IPAddressField(protocol="both")
    p2p_port = serializers.IntegerField(min_value=1, max_value=65535, default=30303)
    rpc_port = serializers.IntegerField(min_value=1, max_value=65535, default=8545)
    ws_port = serializers.IntegerField(min_value=1, max_value=65535, default=8546)
    software_version = serializers.CharField(max_length=32)
    requested_validator = serializers.BooleanField(default=False)

    def validate(self, attrs):
        normalized_enode, enode_key, enode_host, enode_port = parse_enode(attrs["enode"])
        public_key = normalize_public_key(attrs["node_public_key"])
        address = normalize_address(attrs["node_address"])
        try:
            overlay = validate_private_overlay_ip(attrs["host_or_overlay_address"])
        except serializers.ValidationError as exc:
            raise serializers.ValidationError({"host_or_overlay_address": exc.detail}) from exc
        if enode_key != public_key:
            raise serializers.ValidationError({"enode": "The enode identity does not match node_public_key."})
        if enode_host != overlay or enode_port != attrs["p2p_port"]:
            raise serializers.ValidationError({"enode": "The enode host/port must match the declared overlay address and P2P port."})
        if address_from_public_key(public_key) != address:
            raise serializers.ValidationError({"node_address": "The node address does not match the supplied public key."})
        if attrs["rpc_port"] in {attrs["p2p_port"]} or attrs["ws_port"] in {attrs["p2p_port"], attrs["rpc_port"]}:
            raise serializers.ValidationError("P2P, RPC, and WebSocket ports must be distinct.")
        attrs.update(
            enode=normalized_enode,
            node_public_key=public_key,
            node_address=address,
            host_or_overlay_address=overlay,
        )
        return attrs


class NodeHeartbeatSerializer(serializers.Serializer):
    latest_block = serializers.IntegerField(min_value=0)
    network_latest_block = serializers.IntegerField(min_value=0)
    peer_count = serializers.IntegerField(min_value=0, max_value=10000)
    sync_state = serializers.ChoiceField(choices=["CONNECTING", "SYNCING", "ONLINE", "DEGRADED"])
    sync_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=100)
    software_version = serializers.CharField(max_length=32)
    peer_enodes = serializers.ListField(child=serializers.CharField(max_length=255), max_length=256, required=False, default=list)

    def validate_peer_enodes(self, values):
        normalized = []
        for value in values:
            enode, _, _, _ = parse_enode(value)
            if enode not in normalized:
                normalized.append(enode)
        return normalized

    def validate(self, attrs):
        if attrs["network_latest_block"] < attrs["latest_block"]:
            raise serializers.ValidationError({"network_latest_block": "Network height cannot be lower than this node's local height."})
        if attrs["sync_state"] == "ONLINE" and attrs["sync_percentage"] != 100:
            raise serializers.ValidationError({"sync_percentage": "An ONLINE node must report 100% synchronization."})
        return attrs


class BlockchainNodeSerializer(serializers.ModelSerializer):
    owner = serializers.CharField(source="owner.username", allow_null=True, read_only=True)

    class Meta:
        model = BlockchainNode
        fields = (
            "id", "node_uuid", "node_name", "owner", "enode", "node_public_key", "node_address",
            "host_or_overlay_address", "p2p_port", "rpc_port", "ws_port", "node_type", "status",
            "is_validator", "requested_validator", "software_version", "latest_block", "network_latest_block",
            "sync_percentage", "peer_count", "sync_state", "requested_at", "approved_at", "joined_at", "last_seen",
        )
        read_only_fields = fields


class NodePeerSerializer(serializers.ModelSerializer):
    reporter = serializers.UUIDField(source="reporter.node_uuid", read_only=True)

    class Meta:
        model = NodePeerSnapshot
        fields = ("reporter", "peer_enode", "observed_at")
