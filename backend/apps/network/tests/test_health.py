import pytest

from apps.network.models import BlockchainNode
from apps.network.services import refresh_managed_node_health

from .test_enrollment import identity


class ManagedClient:
    url = "http://validator-1:8545"

    def __init__(self, public_key, peer_enode):
        self.public_key = public_key
        self.peer_enode = peer_enode

    def call(self, method, params=None):
        return {
            "admin_nodeInfo": {"id": self.public_key, "enode": "enode://self"},
            "eth_blockNumber": "0x64",
            "net_peerCount": "0x1",
            "eth_syncing": False,
            "admin_peers": [{"enode": self.peer_enode}],
        }[method]


@pytest.mark.django_db
def test_managed_rpc_health_refreshes_bootstrap_node_and_real_peer_edge(monkeypatch):
    data = identity()
    node = BlockchainNode.objects.create(**data, status=BlockchainNode.Status.OFFLINE, is_validator=True, node_type=BlockchainNode.NodeType.VALIDATOR)
    peer = identity(2, host="100.64.0.11")["enode"]
    monkeypatch.setattr("apps.network.services.managed_rpc_clients", lambda: [ManagedClient(node.node_public_key, peer)])

    refreshed = refresh_managed_node_health()

    node.refresh_from_db()
    assert refreshed == 1
    assert node.status == BlockchainNode.Status.ONLINE
    assert node.latest_block == 100
    assert node.network_latest_block == 100
    assert node.peer_count == 1
    assert node.peer_snapshots.filter(peer_enode=peer).exists()
