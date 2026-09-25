import hashlib
import secrets
from datetime import timedelta

from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.hashers import check_password
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.errors import DomainError
from apps.common.permissions import HasPermissionCode
from apps.audit.services import record_audit
from apps.identities.models import DecentralizedIdentity
from apps.identities.permissions import RequiresDIDProof

from .models import Invitation, Profile, User, UserRole, WalletProvision
from .serializers import InvitationActivateSerializer, InvitationCreateSerializer, MeSerializer, WalletProvisionClaimSerializer


class MeView(APIView):
    def get(self, request):
        return Response(MeSerializer(request.user).data)


class WalletProvisionView(APIView):
    def get(self, request):
        provision = WalletProvision.objects.filter(user=request.user).first()
        return Response({
            "issued": provision is not None,
            "claimed": bool(provision and provision.claimed_at),
            "controller_address": provision.controller_address if provision else None,
        })

    @transaction.atomic
    def post(self, request):
        serializer = WalletProvisionClaimSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        provision = WalletProvision.objects.select_for_update().filter(user=request.user).first()
        if provision is None:
            raise DomainError("WALLET_NOT_ISSUED", "Django administration has not issued a wallet for this account.", status_code=404)
        if not check_password(serializer.validated_data["access_code"], provision.access_code_digest):
            raise DomainError("WALLET_ACCESS_CODE_INVALID", "The wallet access code is invalid.", status_code=403)
        identity = DecentralizedIdentity.objects.filter(user=request.user).first()
        if identity is None or identity.controller_address.lower() != provision.controller_address.lower():
            raise DomainError("WALLET_PROVISION_STALE", "The issued wallet does not match the account's active DID controller.", status_code=409)
        is_restore = provision.claimed_at is not None
        if not is_restore:
            provision.claimed_at = timezone.now()
            provision.save(update_fields=["claimed_at", "updated_at"])
        record_audit(
            action="wallet.provision.restored" if is_restore else "wallet.provision.claimed",
            object_type="WalletProvision",
            object_id=provision.id,
            actor=request.user,
            correlation_id=getattr(request, "correlation_id", None),
        )
        return Response({
            "encrypted_wallet": provision.encrypted_wallet,
            "controller_address": provision.controller_address,
        })


class InvitationCreateView(APIView):
    permission_classes = [HasPermissionCode, RequiresDIDProof]
    permission_code = "identity.create"
    did_proof_purpose = "IDENTITY_CHANGE"

    def post(self, request):
        serializer = InvitationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = secrets.token_urlsafe(32)
        invitation = Invitation.objects.create(
            **serializer.validated_data,
            token_digest=hashlib.sha256(token.encode()).hexdigest(),
            expires_at=timezone.now() + timedelta(hours=24),
            created_by=request.user,
        )
        return Response(
            {"invitation_id": invitation.id, "activation_token": token, "expires_at": invitation.expires_at},
            status=status.HTTP_201_CREATED,
        )


class InvitationActivateView(APIView):
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = InvitationActivateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        digest = hashlib.sha256(serializer.validated_data["token"].encode()).hexdigest()
        invitation = Invitation.objects.select_for_update().select_related("role", "department", "created_by").filter(token_digest=digest).first()
        if invitation is None:
            raise DomainError("INVITATION_INVALID", "Invitation is invalid.", status_code=404)
        if invitation.accepted_at is not None:
            raise DomainError("INVITATION_ALREADY_USED", "Invitation has already been accepted.", status_code=409)
        if timezone.now() >= invitation.expires_at:
            raise DomainError("INVITATION_EXPIRED", "Invitation has expired.", status_code=410)
        user = User(
            username=invitation.username,
            email=invitation.email,
            first_name=invitation.first_name,
            last_name=invitation.last_name,
            department=invitation.department,
        )
        validate_password(serializer.validated_data["password"], user=user)
        user.set_password(serializer.validated_data["password"])
        user.save()
        Profile.objects.create(user=user, employee_id=invitation.employee_id)
        UserRole.objects.create(user=user, role=invitation.role, scope_department=invitation.department, granted_by=invitation.created_by)
        invitation.accepted_at = timezone.now()
        invitation.save(update_fields=["accepted_at", "updated_at"])

        return Response(
            {"user_id": user.id, "identity_id": None, "identity_state": "AWAITING_ADMIN_PROVISION"},
            status=status.HTTP_202_ACCEPTED,
        )
