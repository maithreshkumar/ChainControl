from django.conf import settings
from django.db import transaction
from django.utils import timezone
from eth_account import Account

from apps.common.errors import DomainError

from .contracts import get_contract
from .models import BlockchainTransaction
from .nonce_manager import NonceManager


class TransactionService:
    def __init__(self):
        self.nonces = NonceManager()

    @transaction.atomic
    def submit(self, *, contract_name, function_name, args, operation, idempotency_key, actor_did="", related_object_type="", related_object_id="", correlation_id=None):
        row, created = BlockchainTransaction.objects.select_for_update().get_or_create(
            idempotency_key=idempotency_key,
            defaults={
                "operation": operation,
                "actor_did": actor_did,
                "contract_name": contract_name,
                "function_name": function_name,
                "status": BlockchainTransaction.Status.CREATED,
                "related_object_type": related_object_type,
                "related_object_id": str(related_object_id),
                "correlation_id": correlation_id,
            },
        )
        if not created and row.status in {
            BlockchainTransaction.Status.SUBMITTED,
            BlockchainTransaction.Status.PENDING,
            BlockchainTransaction.Status.CONFIRMED,
        }:
            return row
        if not settings.BLOCKCHAIN_SIGNER_PRIVATE_KEY:
            self._fail(row, "SIGNER_NOT_CONFIGURED", "Blockchain signer is not configured.")
            raise DomainError("BLOCKCHAIN_SIGNER_UNAVAILABLE", "Blockchain signer is not configured.", status_code=503)

        web3, contract = get_contract(contract_name)
        account = Account.from_key(settings.BLOCKCHAIN_SIGNER_PRIVATE_KEY)
        signer = account.address
        if settings.BLOCKCHAIN_SIGNER_ADDRESS and signer.lower() != settings.BLOCKCHAIN_SIGNER_ADDRESS.lower():
            self._fail(row, "SIGNER_MISMATCH", "Configured signer address does not match its private key.")
            raise DomainError("BLOCKCHAIN_SIGNER_INVALID", "Blockchain signer configuration is invalid.", status_code=503)
        try:
            with self.nonces.reserve(web3, signer) as nonce:
                fn = getattr(contract.functions, function_name)(*args)
                tx = fn.build_transaction({
                    "from": signer,
                    "nonce": nonce,
                    "chainId": settings.CHAIN_ID,
                    "gas": int(fn.estimate_gas({"from": signer}) * 1.2),
                    "gasPrice": web3.eth.gas_price,
                })
                signed = account.sign_transaction(tx)
                tx_hash = web3.eth.send_raw_transaction(signed.raw_transaction).hex()
                row.nonce = nonce
                row.tx_hash = tx_hash
                row.status = BlockchainTransaction.Status.SUBMITTED
                row.submitted_at = timezone.now()
                row.error_code = ""
                row.error_message = ""
                row.save()
                return row
        except DomainError:
            raise
        except Exception as exc:
            self._fail(row, "BLOCKCHAIN_SUBMISSION_FAILED", str(exc))
            raise DomainError("BLOCKCHAIN_SUBMISSION_FAILED", "Blockchain transaction submission failed.", status_code=503) from exc

    @staticmethod
    def _fail(row, code, message):
        row.status = BlockchainTransaction.Status.FAILED
        row.error_code = code
        row.error_message = message[:2000]
        row.save()

