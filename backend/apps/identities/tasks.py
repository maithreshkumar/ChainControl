from celery import shared_task
from web3 import Web3

from apps.blockchain.transaction_service import TransactionService
from apps.common.errors import DomainError

from .models import DecentralizedIdentity


@shared_task(bind=True, autoretry_for=(), max_retries=0)
def submit_identity_registration(self, identity_id: str, actor_did: str, correlation_id=None):
    identity = DecentralizedIdentity.objects.get(id=identity_id)
    allowed_states = {
        DecentralizedIdentity.State.INVITED,
        DecentralizedIdentity.State.VALIDATION_PENDING,
        DecentralizedIdentity.State.BLOCKCHAIN_PENDING,
    }
    if identity.state not in allowed_states:
        raise DomainError("IDENTITY_STATE_INVALID", "Only a pending identity can be registered.")
    if identity.state != DecentralizedIdentity.State.BLOCKCHAIN_PENDING:
        identity.state = DecentralizedIdentity.State.BLOCKCHAIN_PENDING
        identity.save(update_fields=["state", "updated_at"])
    try:
        row = TransactionService().submit(
            contract_name="IdentityRegistry",
            function_name="registerIdentity",
            args=[Web3.keccak(text=identity.did), Web3.to_checksum_address(identity.controller_address)],
            operation="IDENTITY_REGISTER",
            idempotency_key=f"identity-register:{identity.id}:v{identity.key_version}",
            actor_did=actor_did,
            related_object_type="DecentralizedIdentity",
            related_object_id=identity.id,
            correlation_id=correlation_id or None,
        )
    except Exception:
        DecentralizedIdentity.objects.filter(id=identity.id).update(state=DecentralizedIdentity.State.REGISTRATION_FAILED)
        raise
    return str(row.id)
