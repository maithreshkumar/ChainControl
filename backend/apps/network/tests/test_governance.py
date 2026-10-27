import pytest
from django.contrib.auth import get_user_model

from apps.network.models import BlockchainNode, ValidatorGovernanceOperation
from apps.network.services import NetworkAdmissionError, initiate_validator_change

from .test_enrollment import identity


User = get_user_model()


class RpcClient:
    def __init__(self, url):
        self.url = url
        self.calls = []

    def call(self, method, params):
        self.calls.append((method, params))
        return True


@pytest.mark.django_db
def test_validator_promotion_votes_then_updates_projection_only_after_actual_set_change(monkeypatch):
    operator = User.objects.create_superuser("governor", "governor@example.test", "long-password-123")
    node = BlockchainNode.objects.create(
        **identity(),
        status=BlockchainNode.Status.ONLINE,
        sync_percentage=100,
        latest_block=50,
        network_latest_block=50,
    )
    validators_before = ["0x" + "1" * 40, "0x" + "2" * 40, "0x" + "3" * 40, "0x" + "4" * 40]
    sets = iter([validators_before, validators_before + [node.node_address.lower()]])
    clients = [RpcClient("http://validator-1:8545"), RpcClient("http://validator-2:8545")]
    monkeypatch.setattr("apps.network.services.current_validator_set", lambda: next(sets))
    monkeypatch.setattr("apps.network.services.managed_rpc_clients", lambda: clients)

    operation = initiate_validator_change(node, operator, add=True)

    node.refresh_from_db()
    assert operation.status == ValidatorGovernanceOperation.Status.COMPLETED
    assert node.is_validator is True
    assert node.node_type == BlockchainNode.NodeType.VALIDATOR
    assert all(client.calls == [("qbft_proposeValidatorVote", [node.node_address.lower(), True])] for client in clients)


@pytest.mark.django_db
def test_validator_projection_stays_full_while_real_set_has_not_changed(monkeypatch):
    operator = User.objects.create_superuser("governor2", "governor2@example.test", "long-password-123")
    node = BlockchainNode.objects.create(**identity(), status=BlockchainNode.Status.ONLINE, sync_percentage=100)
    validators = ["0x" + "1" * 40, "0x" + "2" * 40, "0x" + "3" * 40, "0x" + "4" * 40]
    clients = [RpcClient("http://validator-1:8545")]
    monkeypatch.setattr("apps.network.services.current_validator_set", lambda: validators)
    monkeypatch.setattr("apps.network.services.managed_rpc_clients", lambda: clients)

    operation = initiate_validator_change(node, operator, add=True)

    node.refresh_from_db()
    assert operation.status == ValidatorGovernanceOperation.Status.IN_PROGRESS
    assert node.is_validator is False
    assert node.node_type == BlockchainNode.NodeType.FULL_NODE


@pytest.mark.django_db
def test_final_validator_cannot_be_removed(monkeypatch):
    operator = User.objects.create_superuser("governor3", "governor3@example.test", "long-password-123")
    data = identity()
    data["node_address"] = "0x" + "a" * 40
    node = BlockchainNode.objects.create(
        **data,
        status=BlockchainNode.Status.ONLINE,
        sync_percentage=100,
        node_type=BlockchainNode.NodeType.VALIDATOR,
        is_validator=True,
    )
    monkeypatch.setattr("apps.network.services.current_validator_set", lambda: [node.node_address.lower()])

    with pytest.raises(NetworkAdmissionError, match="final active validator"):
        initiate_validator_change(node, operator, add=False)
