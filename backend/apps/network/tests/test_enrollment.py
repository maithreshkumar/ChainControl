from datetime import timedelta

import pytest
from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.utils import timezone
from eth_keys import keys
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.network.models import BlockchainNode, EnrollmentToken, NetworkConfiguration


def identity(seed=1, host="100.64.0.10"):
    private_key = keys.PrivateKey(bytes([seed]) * 32)
    public_key = private_key.public_key.to_bytes().hex()
    address = private_key.public_key.to_checksum_address().lower()
    return {
        "node_uuid": "3d594650-3436-4a1e-a21e-d88a7e372a01",
        "node_name": "Remote Node A",
        "enode": f"enode://{public_key}@{host}:30303",
        "node_public_key": public_key,
        "node_address": address,
        "host_or_overlay_address": host,
        "p2p_port": 30303,
        "rpc_port": 8545,
        "ws_port": 8546,
        "software_version": "1.0.0",
        "requested_validator": False,
    }


@pytest.fixture(autouse=True)
def clear_throttles():
    cache.clear()


@pytest.mark.django_db
def test_single_use_code_creates_pending_node_without_private_key():
    creator = User.objects.create_superuser("operator", "operator@example.test", "long-password-123")
    owner = User.objects.create_user("owner", "owner@example.test", "long-password-123")
    code = "JOIN-strong-code-123456789"
    token = EnrollmentToken.objects.create(
        label="Friend laptop",
        token_digest=make_password(code),
        intended_owner=owner,
        expires_at=timezone.now() + timedelta(hours=1),
        created_by=creator,
    )
    client = APIClient()
    payload = {**identity(), "enrollment_code": code}

    response = client.post("/api/v1/network/enrollment/", payload, format="json")
    replay = client.post("/api/v1/network/enrollment/", {**identity(2), "node_uuid": "3d594650-3436-4a1e-a21e-d88a7e372a02", "enrollment_code": code}, format="json")

    assert response.status_code == 202
    assert response.data["status"] == BlockchainNode.Status.PENDING
    assert response.data["node_credential"].startswith(str(response.data["node_uuid"]))
    assert replay.status_code == 403
    token.refresh_from_db()
    assert token.used_at is not None
    node = BlockchainNode.objects.get(node_uuid=response.data["node_uuid"])
    assert node.owner == owner
    assert not hasattr(node, "private_key")


@pytest.mark.django_db
def test_enrollment_rejects_mismatched_public_identity():
    creator = User.objects.create_superuser("operator2", "operator2@example.test", "long-password-123")
    code = "JOIN-strong-code-987654321"
    EnrollmentToken.objects.create(label="Mismatch", token_digest=make_password(code), expires_at=timezone.now() + timedelta(hours=1), created_by=creator)
    payload = {**identity(), "enrollment_code": code, "node_address": identity(2)["node_address"]}

    response = APIClient().post("/api/v1/network/enrollment/", payload, format="json")

    assert response.status_code == 400
    assert "node_address" in response.data["error"]["details"]
    assert not BlockchainNode.objects.exists()


@pytest.mark.django_db
def test_enrollment_rejects_public_internet_node_address():
    creator = User.objects.create_superuser("operator-public", "operator-public@example.test", "long-password-123")
    code = "JOIN-public-address-123456789"
    EnrollmentToken.objects.create(label="Public address", token_digest=make_password(code), expires_at=timezone.now() + timedelta(hours=1), created_by=creator)
    payload = {**identity(host="8.8.8.8"), "enrollment_code": code}

    response = APIClient().post("/api/v1/network/enrollment/", payload, format="json")

    assert response.status_code == 400
    assert "host_or_overlay_address" in response.data["error"]["details"]
    assert not BlockchainNode.objects.exists()


@pytest.mark.django_db
def test_node_credential_is_scoped_and_pending_node_cannot_fetch_genesis():
    creator = User.objects.create_superuser("operator3", "operator3@example.test", "long-password-123")
    code = "JOIN-status-code-123456789"
    EnrollmentToken.objects.create(label="Status", token_digest=make_password(code), expires_at=timezone.now() + timedelta(hours=1), created_by=creator)
    client = APIClient()
    enrolled = client.post("/api/v1/network/enrollment/", {**identity(), "enrollment_code": code}, format="json")
    credential = enrolled.data["node_credential"]
    node_uuid = enrolled.data["node_uuid"]
    client.credentials(HTTP_AUTHORIZATION=f"Node {credential}")

    status_response = client.get(f"/api/v1/network/enrollment/status/{node_uuid}/")
    other_response = client.get("/api/v1/network/enrollment/status/3d594650-3436-4a1e-a21e-d88a7e372aff/")
    config_response = client.get(f"/api/v1/network/nodes/{node_uuid}/configuration/")

    assert status_response.status_code == 200
    assert status_response.data["status"] == "PENDING"
    assert other_response.status_code == 403
    assert config_response.status_code == 403


@pytest.mark.django_db
def test_approved_node_heartbeat_updates_only_safe_health_fields():
    node_data = identity()
    node = BlockchainNode.objects.create(**node_data, status=BlockchainNode.Status.APPROVED)
    from apps.network.models import NodeCredential
    secret = "node-secret-value-123456789"
    NodeCredential.objects.create(node=node, secret_digest=make_password(secret))
    NetworkConfiguration.objects.create(genesis_hash="a" * 64, genesis_json={"config": {"chainId": 1337}})
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Node {node.node_uuid}.{secret}")

    response = client.post(
        f"/api/v1/network/nodes/{node.node_uuid}/heartbeat/",
        {
            "latest_block": 100,
            "network_latest_block": 120,
            "peer_count": 3,
            "sync_state": "SYNCING",
            "sync_percentage": "83.33",
            "software_version": "1.0.1",
            "peer_enodes": [],
            "private_key": "must-be-ignored",
        },
        format="json",
    )

    assert response.status_code == 200
    node.refresh_from_db()
    assert node.status == BlockchainNode.Status.SYNCING
    assert node.latest_block == 100
    assert node.peer_count == 3
    assert not hasattr(node, "private_key")


@pytest.mark.django_db
def test_online_heartbeat_requires_complete_sync_and_records_transition():
    node = BlockchainNode.objects.create(**identity(), status=BlockchainNode.Status.SYNCING)
    from apps.network.models import NodeCredential
    secret = "node-secret-value-987654321"
    NodeCredential.objects.create(node=node, secret_digest=make_password(secret))
    NetworkConfiguration.objects.create(genesis_hash="e" * 64, genesis_json={"config": {"chainId": 1337}})
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Node {node.node_uuid}.{secret}")
    endpoint = f"/api/v1/network/nodes/{node.node_uuid}/heartbeat/"
    payload = {"latest_block": 120, "network_latest_block": 120, "peer_count": 2, "sync_state": "ONLINE", "sync_percentage": "99.00", "software_version": "1.0.1", "peer_enodes": []}

    invalid = client.post(endpoint, payload, format="json")
    payload["sync_percentage"] = "100.00"
    accepted = client.post(endpoint, payload, format="json")

    assert invalid.status_code == 400
    assert accepted.status_code == 200
    assert AuditEvent.objects.filter(action="NODE_SYNCED", object_id=str(node.id)).count() == 1
