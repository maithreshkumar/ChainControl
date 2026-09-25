import hashlib
from datetime import timedelta

import pytest
from django.contrib.auth.hashers import make_password
from django.urls import reverse
from django.utils import timezone
from eth_account import Account
from rest_framework.test import APIClient

from apps.accounts.admin import WalletProvisionAdminForm
from apps.accounts.models import Invitation, Role, User, WalletProvision
from apps.identities.models import DecentralizedIdentity


def make_account_with_identity(username="provision-user"):
    account = Account.create()
    user = User.objects.create_user(
        username=username,
        email=f"{username}@example.test",
        password="very-long-password",
    )
    DecentralizedIdentity.objects.create(
        user=user,
        did=f"did:ethr:1337:{account.address}",
        controller_address=account.address,
        state=DecentralizedIdentity.State.ACTIVE,
    )
    return user, account


@pytest.mark.django_db
def test_admin_form_encrypts_the_matching_controller_key_without_storing_plaintext():
    user, account = make_account_with_identity()
    access_code = "organization-code-123"
    form = WalletProvisionAdminForm(data={
        "user": user.id,
        "controller_private_key": account.key.hex(),
        "wallet_access_code": access_code,
    })

    assert form.is_valid(), form.errors
    provision = form.save()

    assert provision.controller_address.lower() == account.address.lower()
    assert account.key.hex().lower() not in str(provision.encrypted_wallet).lower()
    assert Account.decrypt(provision.encrypted_wallet, access_code) == account.key


@pytest.mark.django_db
def test_admin_form_rejects_a_key_that_does_not_control_the_account_did():
    user, _ = make_account_with_identity("wrong-key-user")
    form = WalletProvisionAdminForm(data={
        "user": user.id,
        "controller_private_key": Account.create().key.hex(),
        "wallet_access_code": "organization-code-123",
    })

    assert not form.is_valid()
    assert "account DID requires" in str(form.errors)


@pytest.mark.django_db
def test_admin_can_generate_a_controller_for_an_account_without_an_identity():
    user = User.objects.create_user(
        username="new-admin-provisioned-user",
        email="new-admin-provisioned-user@example.test",
        password="very-long-password",
    )
    access_code = "admin-generated-code-123"
    form = WalletProvisionAdminForm(data={
        "user": user.id,
        "generate_controller_key": True,
        "controller_private_key": "",
        "wallet_access_code": access_code,
    })

    assert form.is_valid(), form.errors
    provision = form.save()
    identity = DecentralizedIdentity.objects.get(user=user)

    assert identity.state == DecentralizedIdentity.State.VALIDATION_PENDING
    assert identity.controller_address.lower() == provision.controller_address.lower()
    assert identity.keys.filter(version=1, controller_address__iexact=provision.controller_address).exists()
    assert Account.from_key(Account.decrypt(provision.encrypted_wallet, access_code)).address.lower() == provision.controller_address.lower()


@pytest.mark.django_db
def test_wallet_provision_admin_add_page_exposes_only_admin_provisioning_controls(client):
    admin_user = User.objects.create_superuser(
        username="wallet-admin",
        email="wallet-admin@example.test",
        password="admin-password-123",
    )
    client.force_login(admin_user)

    response = client.get(reverse("admin:accounts_walletprovision_add"))

    assert response.status_code == 200
    assert b"Generate a new controller key" in response.content
    assert b"Wallet access code" in response.content


@pytest.mark.django_db
def test_wallet_provision_selector_only_lists_unprovisioned_non_admin_accounts(client):
    administrator = User.objects.create_superuser(
        username="selector-admin",
        email="selector-admin@example.test",
        password="admin-password-123",
    )
    provisioned_user, provisioned_account = make_account_with_identity("already-provisioned")
    WalletProvision.objects.create(
        user=provisioned_user,
        controller_address=provisioned_account.address,
        encrypted_wallet=Account.encrypt(provisioned_account.key, "existing-code-123"),
        access_code_digest=make_password("existing-code-123"),
    )
    eligible_user, _ = make_account_with_identity("eligible-user")
    staff_user = User.objects.create_user(
        username="django-staff",
        email="django-staff@example.test",
        password="staff-password-123",
        is_staff=True,
    )
    client.force_login(administrator)

    response = client.get(reverse("admin:accounts_walletprovision_add"))
    selectable_usernames = set(
        response.context["adminform"].form.fields["user"].queryset.values_list("username", flat=True)
    )

    assert response.status_code == 200
    assert eligible_user.username in selectable_usernames
    assert provisioned_user.username not in selectable_usernames
    assert administrator.username not in selectable_usernames
    assert staff_user.username not in selectable_usernames


@pytest.mark.django_db
def test_invitee_cannot_choose_or_create_a_controller_wallet():
    creator = User.objects.create_user(
        username="invitation-admin",
        email="invitation-admin@example.test",
        password="admin-password-123",
    )
    role = Role.objects.create(code=Role.Code.USER, name="User")
    token = "one-time-invitation-token"
    Invitation.objects.create(
        email="invitee@example.test",
        username="invitee",
        employee_id="EMP-INVITEE",
        department=None,
        role=role,
        token_digest=hashlib.sha256(token.encode()).hexdigest(),
        expires_at=timezone.now() + timedelta(hours=1),
        created_by=creator,
    )
    client = APIClient()

    response = client.post(
        "/api/v1/invitations/activate/",
        {
            "token": token,
            "password": "InviteePassword123!",
            "controller_address": Account.create().address,
        },
        format="json",
    )

    assert response.status_code == 202
    invitee = User.objects.get(username="invitee")
    assert response.data["identity_state"] == "AWAITING_ADMIN_PROVISION"
    assert not DecentralizedIdentity.objects.filter(user=invitee).exists()
    assert not WalletProvision.objects.filter(user=invitee).exists()


@pytest.mark.django_db
def test_user_can_restore_an_admin_issued_wallet_with_the_correct_access_code():
    user, account = make_account_with_identity("claim-user")
    access_code = "claim-code-12345"
    encrypted_wallet = Account.encrypt(account.key, access_code)
    WalletProvision.objects.create(
        user=user,
        controller_address=account.address,
        encrypted_wallet=encrypted_wallet,
        access_code_digest=make_password(access_code),
    )
    client = APIClient()
    client.force_authenticate(user)

    status_response = client.get("/api/v1/wallet-provision/")
    claimed = client.post("/api/v1/wallet-provision/", {"access_code": access_code}, format="json")
    provision = WalletProvision.objects.get(user=user)
    claimed_at = provision.claimed_at
    restored = client.post("/api/v1/wallet-provision/", {"access_code": access_code}, format="json")
    rejected = client.post("/api/v1/wallet-provision/", {"access_code": "incorrect-code-123"}, format="json")

    assert status_response.status_code == 200
    assert status_response.data == {"issued": True, "claimed": False, "controller_address": account.address}
    assert claimed.status_code == 200
    assert claimed.data["encrypted_wallet"] == encrypted_wallet
    assert restored.status_code == 200
    assert restored.data["encrypted_wallet"] == encrypted_wallet
    assert rejected.status_code == 403
    provision.refresh_from_db()
    assert claimed_at <= timezone.now()
    assert provision.claimed_at == claimed_at
