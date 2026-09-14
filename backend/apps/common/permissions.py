from rest_framework.permissions import BasePermission


class HasPermissionCode(BasePermission):
    permission_code = ""

    def has_permission(self, request, view):
        code = getattr(view, "permission_code", self.permission_code)
        if not code or not request.user.is_authenticated:
            return False
        return request.user.has_platform_permission(code)

