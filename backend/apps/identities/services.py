import hashlib
import secrets
from datetime import timedelta

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from eth_account import Account
from eth_account.messages import encode_defunct

from apps.common.errors import DomainError

from .models import AuthenticationChallenge, DecentralizedIdentity


ALLOWED_PURPOSES = {"LOGIN_PROOF", "ASSET_MINT", "ASSET_ACTIVATE", "ASSET_TRANSFER", "ROLE_CHANGE", "IDENTITY_CHANGE", "IDENTITY_VALIDATE", "ASSET_FREEZE"}


def create_challenge(*, identity: DecentralizedIdentity, purpose: str, correlation_id=None) -> tuple[AuthenticationChallenge, str]:
    if purpose not in ALLOWED_PURPOSES:
        raise DomainError("CHALLENGE_PURPOSE_INVALID", "The requested challenge purpose is not supported.")
    if identity.state != DecentralizedIdentity.State.ACTIVE:
        raise DomainError("IDENTITY_NOT_ACTIVE", "Only an active identity can receive a challenge.", status_code=403)
    from apps.accounts.models import WalletProvision
    if not WalletProvision.objects.filter(
        user_id=identity.user_id,
        claimed_at__isnull=False,
        controller_address__iexact=identity.controller_address,
    ).exists():
        raise DomainError(
            "WALLET_NOT_PROVISIONED",
            "Django administration must issue and the account holder must claim the controller wallet before DID authorization.",
            status_code=403,
        )
    nonce = secrets.token_urlsafe(32)
    expires_at = timezone.now() + timedelta(minutes=3)
    challenge_id = secrets.token_hex(16)
    message = "\n".join([
        "ChainControl DID Authorization",
        f"DID: {identity.did}",
        f"Purpose: {purpose}",
        f"Challenge: {challenge_id}:{nonce}",
        f"Expires: {expires_at.isoformat()}",
    ])
    row = AuthenticationChallenge.objects.create(
        identity=identity,
        purpose=purpose,
        nonce_digest=hashlib.sha256(nonce.encode()).hexdigest(),
        message=message,
        expires_at=expires_at,
        request_correlation_id=correlation_id,
    )
    return row, nonce


@transaction.atomic
def verify_challenge(*, challenge_id, nonce: str, signature: str, user) -> str:
    challenge = AuthenticationChallenge.objects.select_for_update().select_related("identity").filter(id=challenge_id).first()
    if challenge is None or challenge.identity.user_id != user.id:
        raise DomainError("CHALLENGE_NOT_FOUND", "Challenge was not found.", status_code=404)
    if challenge.used_at is not None:
        raise DomainError("CHALLENGE_ALREADY_USED", "Challenge has already been consumed.", status_code=409)
    if timezone.now() >= challenge.expires_at:
        raise DomainError("CHALLENGE_EXPIRED", "Challenge has expired.", status_code=410)
    if not secrets.compare_digest(challenge.nonce_digest, hashlib.sha256(nonce.encode()).hexdigest()):
        raise DomainError("CHALLENGE_INVALID", "Challenge nonce is invalid.", status_code=401)
    if challenge.identity.state != DecentralizedIdentity.State.ACTIVE:
        raise DomainError("IDENTITY_REVOKED", "Identity is not active.", status_code=403)
    try:
        recovered = Account.recover_message(encode_defunct(text=challenge.message), signature=signature)
    except (ValueError, TypeError) as exc:
        raise DomainError("SIGNATURE_INVALID", "Signature could not be verified.", status_code=401) from exc
    if recovered.lower() != challenge.identity.controller_address.lower():
        raise DomainError("SIGNATURE_INVALID", "Signature does not match the active identity controller.", status_code=401)

    challenge.used_at = timezone.now()
    challenge.save(update_fields=["used_at", "updated_at"])
    proof_token = secrets.token_urlsafe(32)
    cache.set(
        f"did-proof:{proof_token}",
        {"user_id": user.id, "identity_id": str(challenge.identity_id), "purpose": challenge.purpose},
        timeout=120,
    )
    return proof_token


def consume_proof(*, proof_token: str, user_id: int, purpose: str) -> bool:
    key = f"did-proof:{proof_token}"
    proof = cache.get(key)
    if proof and proof.get("user_id") == user_id and proof.get("purpose") == purpose:
        cache.delete(key)
        return True
    return False
