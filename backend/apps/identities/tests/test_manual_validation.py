import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import Permission, Role, User, UserRole
from apps.identities.models import DecentralizedIdentity


def make_validator():
    validator = User.objects.create_user(
        username="did-validator",
        email="did-validator@example.test",
        password="very-long-password",
    )
    validate_permission = Permission.objects.create(code="identity.validate", description="Validate identities")
    view_permission = Permission.objects.create(code="identity.view_all", description="View all identities")
    role = Role.objects.create(code=Role.Code.VALIDATOR, name="Validator")
    role.permissions.add(validate_permission, view_permission)
    UserRole.objects.create(user=validator, role=role, granted_by=validator)
    identity = DecentralizedIdentity.objects.create(
        user=validator,
        did="did:ethr:1337:0x3333333333333333333333333333333333333333",
        controller_address="0x3333333333333333333333333333333333333333",
        state=DecentralizedIdentity.State.ACTIVE,
    )
    return validator, identity


@pytest.mark.django_db
def test_validator_moves_submitted_identity_to_blockchain_queue():
    validator, validator_identity = make_validator()
    applicant = User.objects.create_user(
        username="identity-applicant",
        email="identity-applicant@example.test",
        password="very-long-password",
    )
    pending_identity = DecentralizedIdentity.objects.create(
        user=applicant,
        did="did:ethr:1337:0x4444444444444444444444444444444444444444",
        controller_address="0x4444444444444444444444444444444444444444",
        state=DecentralizedIdentity.State.VALIDATION_PENDING,
    )
    proof_token = "identity-validator-proof"
    cache.set(
        f"did-proof:{proof_token}",
        {"user_id": validator.id, "identity_id": str(validator_identity.id), "purpose": "IDENTITY_VALIDATE"},
        timeout=120,
    )

    client = APIClient()
    client.force_authenticate(validator)
    response = client.post(
        reverse("identity-validate", args=[pending_identity.id]),
        HTTP_X_DID_PROOF_TOKEN=proof_token,
    )

    assert response.status_code == 202
    pending_identity.refresh_from_db()
    assert pending_identity.state == DecentralizedIdentity.State.BLOCKCHAIN_PENDING


@pytest.mark.django_db
def test_validator_cannot_validate_own_identity():
    validator, identity = make_validator()
    identity.state = DecentralizedIdentity.State.VALIDATION_PENDING
    identity.save(update_fields=["state"])
    proof_token = "self-validator-proof"
    cache.set(
        f"did-proof:{proof_token}",
        {"user_id": validator.id, "identity_id": str(identity.id), "purpose": "IDENTITY_VALIDATE"},
        timeout=120,
    )

    client = APIClient()
    client.force_authenticate(validator)
    response = client.post(
        reverse("identity-validate", args=[identity.id]),
        HTTP_X_DID_PROOF_TOKEN=proof_token,
    )

    assert response.status_code == 403
    assert response.data["error"]["code"] == "SELF_VALIDATION_FORBIDDEN"
