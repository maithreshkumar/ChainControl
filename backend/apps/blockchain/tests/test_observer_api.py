from types import SimpleNamespace

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Permission, Role, User, UserRole


pytestmark = pytest.mark.django_db


def observer_user(username="observer"):
    user = User.objects.create_user(username=username, email=f"{username}@example.test", password="unused")
    permission = Permission.objects.create(code="observer.view", description="Observer")
    role = Role.objects.create(code=Role.Code.AUDITOR, name="Auditor")
    role.permissions.add(permission)
    UserRole.objects.create(user=user, role=role, granted_by=user)
    return user


class FakeWeb3:
    HTTPProvider = staticmethod(lambda *args, **kwargs: object())

    def __init__(self, *args, **kwargs):
        self.eth = SimpleNamespace(block_number=8)

    def is_connected(self):
        return True


def test_observer_block_feed_is_permissioned_paginated_and_read_only(monkeypatch):
    monkeypatch.setattr("apps.blockchain.views.get_web3", lambda: FakeWeb3())
    monkeypatch.setattr("apps.blockchain.views.block_data", lambda number, **kwargs: {
        "number": number, "hash": f"0x{number:064x}", "transactions": [], "transaction_count": 0,
    })
    client = APIClient()
    denied = client.get("/api/v1/observer/blocks/")
    assert denied.status_code == 401

    client.force_authenticate(observer_user())
    response = client.get("/api/v1/observer/blocks/?limit=3&before=7")
    assert response.status_code == 200
    assert [row["number"] for row in response.data["results"]] == [7, 6, 5]
    assert response.data["next_before"] == 4
    assert client.post("/api/v1/observer/blocks/", {}, format="json").status_code == 405


def test_observer_transaction_detail_uses_decoded_chain_service(monkeypatch):
    tx_hash = "0x" + "a" * 64
    monkeypatch.setattr("apps.blockchain.views.transaction_data", lambda value: {
        "hash": value, "status": "SUCCESS", "decoded": {"contract": "AssetRegistry", "function": "mintAsset"},
        "events": [{"event": "AssetMinted", "parameters": {"tokenId": 1}}],
    })
    client = APIClient()
    client.force_authenticate(observer_user("transaction-observer"))
    response = client.get(f"/api/v1/observer/transactions/{tx_hash}/")
    assert response.status_code == 200
    assert response.data["decoded"]["function"] == "mintAsset"
    assert response.data["events"][0]["event"] == "AssetMinted"
