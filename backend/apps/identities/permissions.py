from rest_framework.permissions import BasePermission

from .services import consume_proof


class RequiresDIDProof(BasePermission):
    def has_permission(self, request, view):
        token = request.headers.get("X-DID-Proof-Token", "")
        purpose = getattr(view, "did_proof_purpose", "")
        return bool(token and purpose and consume_proof(proof_token=token, user_id=request.user.id, purpose=purpose))

