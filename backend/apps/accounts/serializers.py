from rest_framework import serializers

from .models import Department, Invitation, Role, User


class MeSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    department = serializers.CharField(source="department.code", allow_null=True)

    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name", "department", "roles", "permissions")

    def get_roles(self, obj):
        roles = list(obj.role_assignments.filter(active=True).values_list("role__code", flat=True).distinct())
        if obj.is_superuser and "ADMIN" not in roles:
            roles.append("ADMIN")
        return roles

    def get_permissions(self, obj):
        if obj.is_superuser:
            from .models import Permission
            return list(Permission.objects.values_list("code", flat=True).distinct())
        return list(obj.role_assignments.filter(active=True).values_list("role__permissions__code", flat=True).distinct())


class InvitationCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    username = serializers.CharField(max_length=150)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    employee_id = serializers.CharField(max_length=64)
    department = serializers.PrimaryKeyRelatedField(queryset=Department.objects.all(), allow_null=True)
    role = serializers.PrimaryKeyRelatedField(queryset=Role.objects.all())

    def validate(self, attrs):
        if User.objects.filter(email__iexact=attrs["email"]).exists() or Invitation.objects.filter(email__iexact=attrs["email"], accepted_at__isnull=True).exists():
            raise serializers.ValidationError({"email": "An account or active invitation already uses this email."})
        if User.objects.filter(username__iexact=attrs["username"]).exists():
            raise serializers.ValidationError({"username": "This username is already in use."})
        return attrs


class InvitationActivateSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=256)
    password = serializers.CharField(min_length=12, max_length=256, write_only=True)


class WalletProvisionClaimSerializer(serializers.Serializer):
    access_code = serializers.CharField(min_length=12, max_length=256, write_only=True)
