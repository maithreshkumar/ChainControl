from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record_audit
from apps.common.errors import DomainError
from apps.common.permissions import HasPermissionCode
from .permissions import RequiresDIDProof

from .models import DecentralizedIdentity, IdentityKey
from .serializers import ChallengeCreateSerializer, ChallengeVerifySerializer, IdentitySerializer
from .services import create_challenge, verify_challenge


class IdentityViewSet(viewsets.ModelViewSet):
    serializer_class = IdentitySerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        if user.has_platform_permission("identity.view_all"):
            return DecentralizedIdentity.objects.select_related("user").all()
        if user.department_id and user.has_platform_permission("identity.view", department_id=user.department_id):
            return DecentralizedIdentity.objects.select_related("user").filter(user__department_id=user.department_id)
        return DecentralizedIdentity.objects.select_related("user").filter(user=user)

    def get_permissions(self):
        if self.action == "create":
            self.permission_code = "identity.create"
            self.did_proof_purpose = "IDENTITY_CHANGE"
            return [HasPermissionCode(), RequiresDIDProof()]
        if self.action == "validate":
            self.permission_code = "identity.validate"
            self.did_proof_purpose = "IDENTITY_VALIDATE"
            return [HasPermissionCode(), RequiresDIDProof()]
        return super().get_permissions()

    def perform_create(self, serializer):
        identity = serializer.save(state=DecentralizedIdentity.State.VALIDATION_PENDING)
        IdentityKey.objects.create(
            identity=identity,
            version=identity.key_version,
            controller_address=identity.controller_address,
            active_from=identity.created_at,
        )
        record_audit(
            action="identity.validation.requested",
            object_type="DecentralizedIdentity",
            object_id=identity.id,
            actor=self.request.user,
            correlation_id=getattr(self.request, "correlation_id", None),
        )

    @action(detail=False, methods=["get"])
    def me(self, request):
        identity = DecentralizedIdentity.objects.filter(user=request.user).first()
        if identity is None:
            raise DomainError("IDENTITY_NOT_FOUND", "The current account has no identity.", status_code=404)
        return Response(self.get_serializer(identity).data)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def validate(self, request, pk=None):
        identity = DecentralizedIdentity.objects.select_for_update().select_related("user").filter(pk=pk).first()
        if identity is None:
            raise DomainError("IDENTITY_NOT_FOUND", "Identity was not found.", status_code=404)
        if identity.state not in {DecentralizedIdentity.State.INVITED, DecentralizedIdentity.State.VALIDATION_PENDING}:
            raise DomainError("IDENTITY_NOT_PENDING", "Only an identity waiting for validation can be approved.", status_code=409)
        if identity.user_id == request.user.id:
            raise DomainError("SELF_VALIDATION_FORBIDDEN", "Validators cannot approve their own identity.", status_code=403)

        identity.state = DecentralizedIdentity.State.BLOCKCHAIN_PENDING
        identity.save(update_fields=["state", "updated_at"])
        from .tasks import submit_identity_registration
        transaction.on_commit(lambda: submit_identity_registration.delay(
            str(identity.id),
            request.user.identity.did,
            str(getattr(request, "correlation_id", "")),
        ))
        record_audit(
            action="identity.validation.approved",
            object_type="DecentralizedIdentity",
            object_id=identity.id,
            actor=request.user,
            correlation_id=getattr(request, "correlation_id", None),
        )
        return Response(self.get_serializer(identity).data, status=status.HTTP_202_ACCEPTED)


class ChallengeCreateView(APIView):
    def post(self, request):
        serializer = ChallengeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        identity = DecentralizedIdentity.objects.get(user=request.user)
        row, nonce = create_challenge(
            identity=identity,
            purpose=serializer.validated_data["purpose"],
            correlation_id=getattr(request, "correlation_id", None),
        )
        return Response({"challenge_id": row.id, "nonce": nonce, "message": row.message, "expires_at": row.expires_at}, status=status.HTTP_201_CREATED)


class ChallengeVerifyView(APIView):
    def post(self, request):
        serializer = ChallengeVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = verify_challenge(user=request.user, **serializer.validated_data)
        return Response({"proof_token": token, "expires_in": 120})
