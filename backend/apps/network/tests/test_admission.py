import pytest
from django.contrib.auth.hashers import make_password

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.network.models import BlockchainNode, NetworkConfiguration, NodeCredential, ValidatorGovernanceOperation
from apps.network.services import NetworkAdmissionError, approve_node, bootstrap_configuration_for, distributable_node_allowlist, external_bootnodes, propagate_allowlist_change, revoke_node
from apps.network.tests.test_enrollment import identity


@pytest.mark.django_db
def test_approval_requires_real_permission_propagation(monkeypatch):
    operator = User.objects.create_superuser("network-admin", "network-admin@example.test", "long-password-123")
    node = BlockchainNode.objects.create(**identity(), status=BlockchainNode.Status.PENDING)
    NodeCredential.objects.create(node=node, secret_digest=make_password("node-secret-value-123"))
    NetworkConfiguration.objects.create(genesis_hash="b" * 64, genesis_json={"config": {"chainId": 1337}}, genesis_text='{"config":{"chainId":1337}}')
    persisted = []
    monkeypatch.setattr("apps.network.services.load_static_enodes", lambda: ["enode://" + "1" * 128 + "@100.64.0.1:30303"])
    monkeypatch.setattr("apps.network.services.propagate_allowlist_change", lambda enode, add: ["http://validator-1:8545"] if add else [])
    monkeypatch.setattr("apps.network.services.persist_permission_file", lambda enodes: persisted.extend(enodes))
    monkeypatch.setattr("apps.network.services.persist_runtime_static_nodes_file", lambda enodes: None)

    approved = approve_node(node, operator)

    assert approved.status == BlockchainNode.Status.APPROVED
    assert node.enode in persisted
    assert AuditEvent.objects.filter(action="NODE_APPROVED", object_id=str(node.id), outcome="SUCCESS").exists()


@pytest.mark.django_db
def test_failed_permission_propagation_does_not_fake_approval(monkeypatch):
    operator = User.objects.create_superuser("network-admin2", "network-admin2@example.test", "long-password-123")
    node = BlockchainNode.objects.create(**identity(), status=BlockchainNode.Status.PENDING)
    NodeCredential.objects.create(node=node, secret_digest=make_password("node-secret-value-123"))
    NetworkConfiguration.objects.create(genesis_hash="c" * 64, genesis_json={"config": {"chainId": 1337}}, genesis_text='{"config":{"chainId":1337}}')
    monkeypatch.setattr("apps.network.services.propagate_allowlist_change", lambda *args, **kwargs: (_ for _ in ()).throw(NetworkAdmissionError("validator unreachable")))

    with pytest.raises(NetworkAdmissionError):
        approve_node(node, operator)

    node.refresh_from_db()
    assert node.status == BlockchainNode.Status.PENDING
    assert "validator unreachable" in node.configuration_error
    assert AuditEvent.objects.filter(action="NODE_APPROVED", object_id=str(node.id), outcome="FAILED").exists()


@pytest.mark.django_db
def test_permission_propagation_is_idempotent_when_node_is_already_allowed(monkeypatch):
    node = BlockchainNode.objects.create(**identity(), status=BlockchainNode.Status.PENDING)
    mutations = []

    class AlreadyAllowedClient:
        url = "http://validator-1:8545"

        def call(self, method, params):
            if method == "perm_getNodesAllowlist":
                return [node.enode]
            mutations.append((method, params))
            return True

    monkeypatch.setattr("apps.network.services.managed_rpc_clients", lambda: [AlreadyAllowedClient()])

    propagated = propagate_allowlist_change(node.enode, add=True)

    assert propagated == ["http://validator-1:8545"]
    assert mutations == [("admin_addPeer", [node.enode])]


@pytest.mark.django_db
def test_revocation_removes_permission_before_marking_node_revoked(monkeypatch):
    operator = User.objects.create_superuser("network-admin3", "network-admin3@example.test", "long-password-123")
    node = BlockchainNode.objects.create(**identity(), status=BlockchainNode.Status.ONLINE)
    NodeCredential.objects.create(node=node, secret_digest=make_password("node-secret-value-123"))
    NetworkConfiguration.objects.create(genesis_hash="d" * 64, genesis_json={"config": {"chainId": 1337}})
    calls = []
    monkeypatch.setattr("apps.network.services.load_static_enodes", lambda: [])
    monkeypatch.setattr("apps.network.services.propagate_allowlist_change", lambda enode, add: calls.append((enode, add)) or ["http://validator-1:8545"])
    monkeypatch.setattr("apps.network.services.persist_permission_file", lambda enodes: None)
    monkeypatch.setattr("apps.network.services.persist_runtime_static_nodes_file", lambda enodes: None)

    revoked = revoke_node(node, operator, "retired")

    assert calls == [(node.enode, False)]
    assert revoked.status == BlockchainNode.Status.REVOKED
    assert revoked.revocation_reason == "retired"


@pytest.mark.django_db
def test_pending_validator_votes_are_released_only_to_existing_validators(monkeypatch):
    operator = User.objects.create_superuser("network-admin4", "network-admin4@example.test", "long-password-123")
    full_node = BlockchainNode.objects.create(**identity(), status=BlockchainNode.Status.ONLINE)
    validator_data = identity(2, host="100.64.0.11")
    validator_data["node_uuid"] = "3d594650-3436-4a1e-a21e-d88a7e372a02"
    validator = BlockchainNode.objects.create(**validator_data, status=BlockchainNode.Status.ONLINE, is_validator=True, node_type=BlockchainNode.NodeType.VALIDATOR)
    NetworkConfiguration.objects.create(genesis_hash="f" * 64, genesis_json={"config": {"chainId": 1337}}, genesis_text='{"config":{"chainId":1337}}')
    operation = ValidatorGovernanceOperation.objects.create(
        node=full_node,
        action=ValidatorGovernanceOperation.Action.ADD,
        status=ValidatorGovernanceOperation.Status.IN_PROGRESS,
        candidate_address=full_node.node_address,
        requested_by=operator,
    )
    monkeypatch.setattr("apps.network.services.load_static_enodes", lambda: [])

    full_config = bootstrap_configuration_for(full_node)
    validator_config = bootstrap_configuration_for(validator)

    assert full_config["validator_votes"] == []
    assert validator_config["validator_votes"] == [{"operation_id": str(operation.id), "candidate_address": full_node.node_address, "add": True}]


@pytest.mark.django_db
def test_external_bootnodes_rewrite_only_managed_validator_endpoints(monkeypatch, settings):
    settings.BESU_EXTERNAL_P2P_HOST = "100.114.144.74"
    settings.BESU_EXTERNAL_P2P_BASE_PORT = 30303
    monkeypatch.setattr(
        "apps.network.services.load_static_enodes",
        lambda: [
            "enode://" + "1" * 128 + "@172.20.0.11:30303",
            "enode://" + "2" * 128 + "@172.20.0.12:30303",
        ],
    )

    assert external_bootnodes() == [
        "enode://" + "1" * 128 + "@100.114.144.74:30303",
        "enode://" + "2" * 128 + "@100.114.144.74:30304",
    ]
    assert distributable_node_allowlist() == [
        "enode://" + "1" * 128 + "@172.20.0.11:30303",
        "enode://" + "2" * 128 + "@172.20.0.12:30303",
        "enode://" + "1" * 128 + "@100.114.144.74:30303",
        "enode://" + "2" * 128 + "@100.114.144.74:30304",
    ]
