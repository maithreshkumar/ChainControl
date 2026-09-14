import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import Permission, Role, User, UserRole
from apps.assets.models import Asset, AssetVersion
from apps.blockchain.models import BlockchainEvent, BlockchainTransaction
from apps.identities.models import DecentralizedIdentity


@pytest.mark.django_db
def test_verifier_manually_activates_confirmed_physical_asset():
    user = User.objects.create_user(
        username="verifier",
        email="verifier@example.test",
        password="very-long-password",
    )
    permission = Permission.objects.create(code="asset.activate", description="Activate assets")
    view_permission = Permission.objects.create(code="asset.view_all", description="View all assets")
    role = Role.objects.create(code=Role.Code.VALIDATOR, name="Validator")
    role.permissions.add(permission, view_permission)
    UserRole.objects.create(user=user, role=role, granted_by=user)
    identity = DecentralizedIdentity.objects.create(
        user=user,
        did="did:ethr:1337:0x1111111111111111111111111111111111111111",
        controller_address="0x1111111111111111111111111111111111111111",
        state=DecentralizedIdentity.State.ACTIVE,
    )
    submitter = User.objects.create_user(
        username="asset-submitter",
        email="asset-submitter@example.test",
        password="very-long-password",
    )
    asset = Asset.objects.create(
        name="Verified equipment",
        kind=Asset.Kind.PHYSICAL,
        classification=10,
        created_by=submitter,
        state=Asset.State.BLOCKCHAIN_PENDING,
        serial_number="SERIAL-VERIFY-1",
    )
    AssetVersion.objects.create(asset=asset, version=1, content_hash="a" * 64, metadata_hash="b" * 64)
    transaction = BlockchainTransaction.objects.create(
        idempotency_key=f"asset-mint:{asset.id}:v1",
        operation="ASSET_MINT",
        contract_name="AssetRegistry",
        function_name="mintAsset",
        tx_hash="0x" + "1" * 64,
        status=BlockchainTransaction.Status.CONFIRMED,
        related_object_type="Asset",
        related_object_id=str(asset.id),
    )
    BlockchainEvent.objects.create(
        tx_hash=transaction.tx_hash,
        log_index=0,
        block_number=10,
        contract_name="AssetRegistry",
        event_name="AssetMinted",
        args={"tokenId": 7},
    )
    proof_token = "manual-verifier-proof"
    cache.set(
        f"did-proof:{proof_token}",
        {"user_id": user.id, "identity_id": str(identity.id), "purpose": "ASSET_ACTIVATE"},
        timeout=120,
    )

    client = APIClient()
    client.force_authenticate(user)
    response = client.post(
        reverse("asset-activate", args=[asset.id]),
        HTTP_X_DID_PROOF_TOKEN=proof_token,
    )

    assert response.status_code == 200
    asset.refresh_from_db()
    assert asset.state == Asset.State.ACTIVE
    assert asset.token_id == 7


@pytest.mark.django_db
def test_verifier_cannot_activate_before_chain_confirmation():
    user = User.objects.create_user(
        username="early-verifier",
        email="early-verifier@example.test",
        password="very-long-password",
    )
    permission = Permission.objects.create(code="asset.activate", description="Activate assets")
    view_permission = Permission.objects.create(code="asset.view_all", description="View all assets")
    role = Role.objects.create(code=Role.Code.VALIDATOR, name="Validator")
    role.permissions.add(permission, view_permission)
    UserRole.objects.create(user=user, role=role, granted_by=user)
    identity = DecentralizedIdentity.objects.create(
        user=user,
        did="did:ethr:1337:0x2222222222222222222222222222222222222222",
        controller_address="0x2222222222222222222222222222222222222222",
        state=DecentralizedIdentity.State.ACTIVE,
    )
    submitter = User.objects.create_user(
        username="early-asset-submitter",
        email="early-asset-submitter@example.test",
        password="very-long-password",
    )
    asset = Asset.objects.create(
        name="Unconfirmed equipment",
        kind=Asset.Kind.PHYSICAL,
        classification=10,
        created_by=submitter,
        state=Asset.State.BLOCKCHAIN_PENDING,
        serial_number="SERIAL-VERIFY-2",
    )
    AssetVersion.objects.create(asset=asset, version=1, content_hash="a" * 64, metadata_hash="b" * 64)
    proof_token = "early-verifier-proof"
    cache.set(
        f"did-proof:{proof_token}",
        {"user_id": user.id, "identity_id": str(identity.id), "purpose": "ASSET_ACTIVATE"},
        timeout=120,
    )

    client = APIClient()
    client.force_authenticate(user)
    response = client.post(
        reverse("asset-activate", args=[asset.id]),
        HTTP_X_DID_PROOF_TOKEN=proof_token,
    )

    assert response.status_code == 409
    asset.refresh_from_db()
    assert asset.state == Asset.State.BLOCKCHAIN_PENDING
