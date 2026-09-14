from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from apps.common.models import UUIDTimeStampedModel


class Department(UUIDTimeStampedModel):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=120)

    def __str__(self):
        return self.code


class User(AbstractUser):
    email = models.EmailField(unique=True)
    department = models.ForeignKey(Department, null=True, blank=True, on_delete=models.PROTECT, related_name="users")

    def has_platform_permission(self, code: str, *, department_id=None) -> bool:
        assignments = self.role_assignments.filter(active=True, role__permissions__code=code).distinct()
        if department_id is not None:
            assignments = assignments.filter(models.Q(scope_department_id=department_id) | models.Q(scope_department__isnull=True))
        return assignments.exists()


class Profile(UUIDTimeStampedModel):
    class Clearance(models.IntegerChoices):
        PUBLIC = 0, "Public"
        INTERNAL = 10, "Internal"
        CONFIDENTIAL = 20, "Confidential"
        RESTRICTED = 30, "Restricted"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    employee_id = models.CharField(max_length=64, unique=True)
    clearance = models.PositiveSmallIntegerField(choices=Clearance, default=Clearance.INTERNAL)

    def __str__(self):
        return f"{self.user.username} · {self.employee_id}"


class WalletProvision(UUIDTimeStampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="wallet_provision")
    controller_address = models.CharField(max_length=42)
    encrypted_wallet = models.JSONField()
    access_code_digest = models.CharField(max_length=255)
    claimed_at = models.DateTimeField(null=True, blank=True)
    issued_by = models.ForeignKey(User, null=True, on_delete=models.PROTECT, related_name="issued_wallet_provisions")

    def __str__(self):
        return f"{self.user.username} · {self.controller_address}"


class Permission(UUIDTimeStampedModel):
    code = models.CharField(max_length=80, unique=True)
    description = models.CharField(max_length=255)

    def __str__(self):
        return self.code


class Role(UUIDTimeStampedModel):
    class Code(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        VALIDATOR = "VALIDATOR", "Validator"
        MANAGER = "MANAGER", "Manager"
        AUDITOR = "AUDITOR", "Auditor"
        USER = "USER", "User"

    code = models.CharField(max_length=20, choices=Code, unique=True)
    name = models.CharField(max_length=80)
    permissions = models.ManyToManyField(Permission, related_name="roles", blank=True)

    def __str__(self):
        return self.code


class UserRole(UUIDTimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="role_assignments")
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="assignments")
    scope_department = models.ForeignKey(Department, null=True, blank=True, on_delete=models.PROTECT)
    active = models.BooleanField(default=True)
    granted_by = models.ForeignKey(User, null=True, on_delete=models.PROTECT, related_name="granted_role_assignments")
    granted_at = models.DateTimeField(default=timezone.now)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "role", "scope_department"], name="unique_user_role_scope")]


class Invitation(UUIDTimeStampedModel):
    email = models.EmailField()
    username = models.CharField(max_length=150)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    employee_id = models.CharField(max_length=64)
    department = models.ForeignKey(Department, null=True, on_delete=models.PROTECT)
    role = models.ForeignKey(Role, on_delete=models.PROTECT)
    token_digest = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="created_invitations")

    class Meta:
        indexes = [models.Index(fields=["email", "expires_at"])]
