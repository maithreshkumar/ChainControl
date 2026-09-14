import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import Department, Permission, Role, User, UserRole
from apps.assets.models import Asset
from apps.identities.models import DecentralizedIdentity


def grant(user, role_code, *permission_codes):
    role = Role.objects.create(code=role_code, name=Role.Code(role_code).label)
    permissions = [
        Permission.objects.create(code=code, description=code)
        for code in permission_codes
    ]
    role.permissions.add(*permissions)
    UserRole.objects.create(user=user, role=role, granted_by=user)


@pytest.mark.django_db
def test_successful_asset_submission_is_visible_in_the_validator_queue():
    department = Department.objects.create(code="QUEUE", name="Queue Department")
    submitter = User.objects.create_user(
        username="queue-submitter",
        email="queue-submitter@example.test",
        password="very-long-password",
        department=department,
    )
    submitter_identity = DecentralizedIdentity.objects.create(
        user=submitter,
        did="did:ethr:1337:0x5555555555555555555555555555555555555555",
        controller_address="0x5555555555555555555555555555555555555555",
        state=DecentralizedIdentity.State.ACTIVE,
    )
    grant(submitter, Role.Code.USER, "asset.mint")

    validator = User.objects.create_user(
        username="queue-validator",
        email="queue-validator@example.test",
        password="very-long-password",
    )
    grant(validator, Role.Code.VALIDATOR, "asset.view_all")

    proof_token = "asset-submission-proof"
    cache.set(
        f"did-proof:{proof_token}",
        {"user_id": submitter.id, "identity_id": str(submitter_identity.id), "purpose": "ASSET_MINT"},
        timeout=120,
    )
    client = APIClient()
    client.force_authenticate(submitter)

    submitted = client.post(
        reverse("asset-list"),
        {
            "name": "Validator queue equipment",
            "kind": Asset.Kind.PHYSICAL,
            "classification": 10,
            "serial_number": "QUEUE-SERIAL-1",
            "custody_identifier": "QUEUE-CUSTODY-1",
        },
        HTTP_X_DID_PROOF_TOKEN=proof_token,
    )

    assert submitted.status_code == 202
    assert submitted.data["state"] == Asset.State.BLOCKCHAIN_PENDING
    created_asset = Asset.objects.get(id=submitted.data["id"])
    assert created_asset.owner_projection == submitter_identity
    assert created_asset.department == department

    submitter_registry = client.get(reverse("asset-list"))
    assert submitter_registry.status_code == 200
    submitter_ids = {str(asset["id"]) for asset in submitter_registry.data["results"]}
    assert str(submitted.data["id"]) in submitter_ids

    client.force_authenticate(validator)
    queue = client.get(reverse("asset-list"))

    assert queue.status_code == 200
    queued_ids = {str(asset["id"]) for asset in queue.data["results"]}
    assert str(submitted.data["id"]) in queued_ids


@pytest.mark.django_db
def test_submitter_can_see_an_existing_asset_with_missing_projection():
    submitter = User.objects.create_user(
        username="legacy-submitter",
        email="legacy-submitter@example.test",
        password="very-long-password",
    )
    grant(submitter, Role.Code.USER, "asset.view")
    asset = Asset.objects.create(
        name="Previously submitted asset",
        kind=Asset.Kind.PHYSICAL,
        classification=10,
        created_by=submitter,
        state=Asset.State.BLOCKCHAIN_PENDING,
        serial_number="LEGACY-QUEUE-SERIAL",
    )
    client = APIClient()
    client.force_authenticate(submitter)

    response = client.get(reverse("asset-list"))

    assert response.status_code == 200
    visible_ids = {str(item["id"]) for item in response.data["results"]}
    assert str(asset.id) in visible_ids
