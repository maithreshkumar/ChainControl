import pytest
from django.utils import timezone
from eth_account import Account
from eth_account.messages import encode_defunct

from apps.accounts.models import User, WalletProvision
from apps.common.errors import DomainError
from apps.identities.models import DecentralizedIdentity
from apps.identities.services import create_challenge, verify_challenge


def provision_wallet(user, account):
    WalletProvision.objects.create(
        user=user,
        controller_address=account.address,
        encrypted_wallet={},
        access_code_digest="test-only",
        claimed_at=timezone.now(),
    )


@pytest.mark.django_db
def test_valid_challenge_is_consumed_and_replay_rejected():
    account = Account.create()
    user = User.objects.create_user(username="alice", email="alice@example.test", password="very-long-password")
    identity = DecentralizedIdentity.objects.create(
        user=user,
        did=f"did:ethr:1337:{account.address}",
        controller_address=account.address,
        state=DecentralizedIdentity.State.ACTIVE,
    )
    provision_wallet(user, account)
    challenge, nonce = create_challenge(identity=identity, purpose="ASSET_TRANSFER")
    signature = Account.sign_message(encode_defunct(text=challenge.message), account.key).signature.hex()

    proof = verify_challenge(challenge_id=challenge.id, nonce=nonce, signature=signature, user=user)
    assert proof

    with pytest.raises(DomainError) as replay:
        verify_challenge(challenge_id=challenge.id, nonce=nonce, signature=signature, user=user)
    assert replay.value.code == "CHALLENGE_ALREADY_USED"


@pytest.mark.django_db
def test_valid_signature_from_revoked_identity_is_rejected():
    account = Account.create()
    user = User.objects.create_user(username="revoked", email="revoked@example.test", password="very-long-password")
    identity = DecentralizedIdentity.objects.create(
        user=user,
        did=f"did:ethr:1337:{account.address}",
        controller_address=account.address,
        state=DecentralizedIdentity.State.ACTIVE,
    )
    provision_wallet(user, account)
    challenge, nonce = create_challenge(identity=identity, purpose="ROLE_CHANGE")
    signature = Account.sign_message(encode_defunct(text=challenge.message), account.key).signature.hex()
    identity.state = DecentralizedIdentity.State.REVOKED
    identity.save(update_fields=["state", "updated_at"])

    with pytest.raises(DomainError) as rejected:
        verify_challenge(challenge_id=challenge.id, nonce=nonce, signature=signature, user=user)
    assert rejected.value.code == "IDENTITY_REVOKED"


@pytest.mark.django_db
def test_challenge_is_rejected_without_an_admin_provisioned_wallet():
    account = Account.create()
    user = User.objects.create_user(username="unprovisioned", email="unprovisioned@example.test", password="very-long-password")
    identity = DecentralizedIdentity.objects.create(
        user=user,
        did=f"did:ethr:1337:{account.address}",
        controller_address=account.address,
        state=DecentralizedIdentity.State.ACTIVE,
    )

    with pytest.raises(DomainError) as rejected:
        create_challenge(identity=identity, purpose="ASSET_TRANSFER")

    assert rejected.value.code == "WALLET_NOT_PROVISIONED"
