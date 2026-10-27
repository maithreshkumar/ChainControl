from rest_framework.permissions import BasePermission

from .models import BlockchainNode


class IsAuthenticatedNode(BasePermission):
    def has_permission(self, request, view):
        return isinstance(request.auth, BlockchainNode)

    def has_object_permission(self, request, view, obj):
        return isinstance(request.auth, BlockchainNode) and request.auth.pk == obj.pk


class IsDjangoSuperuser(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)
