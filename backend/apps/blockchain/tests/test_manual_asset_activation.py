import pytest

from apps.accounts.models import User
from apps.assets.models import Asset
from apps.blockchain import tasks
from apps.blockchain.models import BlockchainTransaction
from apps.identities.models import DecentralizedIdentity


class FakeAssetMintedEvent:
    def process_receipt(self, receipt):
        return [{"logIndex": 0, "blockNumber": 12, "args": {"tokenId": 9}}]


class FakeEvents:
    @staticmethod
    def AssetMinted():
        return FakeAssetMintedEvent()


class FakeContract:
    events = FakeEvents()


@pytest.mark.django_db
def test_receipt_indexing_leaves_asset_pending_for_manual_verifier(monkeypatch):
    user = User.objects.create_user(
        username="asset-owner",
        email="asset-owner@example.test",
        password="very-long-password",
    )
    asset = Asset.objects.create(
        name="Pending verification",
        kind=Asset.Kind.PHYSICAL,
        classification=10,
        created_by=user,
        state=Asset.State.BLOCKCHAIN_PENDING,
        serial_number="MANUAL-VERIFY-1",
    )
    transaction = BlockchainTransaction.objects.create(
        idempotency_key=f"asset-mint:{asset.id}:v1",
        operation="ASSET_MINT",
        contract_name="AssetRegistry",
        function_name="mintAsset",
        tx_hash="0x" + "9" * 64,
        status=BlockchainTransaction.Status.CONFIRMED,
        related_object_type="Asset",
        related_object_id=str(asset.id),
    )
    monkeypatch.setattr(tasks, "get_contract", lambda name: (None, FakeContract()))

    tasks._index_known_events(transaction, object())

    asset.refresh_from_db()
    assert asset.token_id == 9
    assert asset.state == Asset.State.BLOCKCHAIN_PENDING


@pytest.mark.django_db
def test_reconciliation_repairs_a_missing_owner_projection(monkeypatch):
    user = User.objects.create_user(
        username="reconciled-owner",
        email="reconciled-owner@example.test",
        password="very-long-password",
    )
    identity = DecentralizedIdentity.objects.create(
        user=user,
        did="did:ethr:1337:0x6666666666666666666666666666666666666666",
        controller_address="0x6666666666666666666666666666666666666666",
        state=DecentralizedIdentity.State.ACTIVE,
    )
    asset = Asset.objects.create(
        name="Missing owner projection",
        kind=Asset.Kind.PHYSICAL,
        classification=10,
        created_by=user,
        state=Asset.State.ACTIVE,
        serial_number="RECONCILE-OWNER-1",
        token_id=12,
    )

    class OwnerCall:
        def call(self):
            return identity.controller_address

    class Functions:
        @staticmethod
        def ownerOf(token_id):
            assert token_id == 12
            return OwnerCall()

    class OwnerContract:
        functions = Functions()

    monkeypatch.setattr(tasks, "get_contract", lambda name: (None, OwnerContract()))

    tasks.reconcile_asset_ownership()

    asset.refresh_from_db()
    assert asset.owner_projection == identity
