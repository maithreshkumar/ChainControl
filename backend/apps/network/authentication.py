from dataclasses import dataclass

from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from .models import BlockchainNode, NodeCredential


@dataclass(frozen=True)
class NodePrincipal:
    node_uuid: str
    is_authenticated: bool = True
    is_active: bool = True
    is_staff: bool = False
    is_superuser: bool = False

    @property
    def username(self):
        return f"node:{self.node_uuid}"


class NodeCredentialAuthentication(BaseAuthentication):
    keyword = "Node"

    def authenticate(self, request):
        header = get_authorization_header(request).decode("utf-8")
        if not header:
            return None
        prefix, separator, value = header.partition(" ")
        if prefix.lower() != self.keyword.lower() or not separator:
            return None
        node_uuid, separator, secret = value.partition(".")
        if not separator or not secret:
            raise AuthenticationFailed("Malformed node credential.")
        try:
            credential = NodeCredential.objects.select_related("node", "node__owner").get(node__node_uuid=node_uuid)
        except (NodeCredential.DoesNotExist, ValueError) as exc:
            raise AuthenticationFailed("Invalid node credential.") from exc
        if not credential.matches(secret):
            raise AuthenticationFailed("Invalid node credential.")
        credential.last_used_at = timezone.now()
        credential.save(update_fields=["last_used_at", "updated_at"])
        principal = credential.node.owner or NodePrincipal(str(credential.node.node_uuid))
        return principal, credential.node
