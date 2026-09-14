from getpass import getpass

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import transaction
from eth_utils import is_address, to_checksum_address

from apps.accounts.models import Department, Profile, Role, User, UserRole
from apps.blockchain.transaction_service import TransactionService
from apps.identities.models import DecentralizedIdentity, IdentityKey
from web3 import Web3


class Command(BaseCommand):
    help = "Create the first business Admin and submit its DID registration without granting Django superuser status."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--email", required=True)
        parser.add_argument("--employee-id", required=True)
        parser.add_argument("--department", default="GOVERNANCE")
        parser.add_argument("--controller-address", required=True)
        parser.add_argument("--password", required=False, default="")

    @transaction.atomic
    def handle(self, *args, **options):
        if User.objects.filter(username=options["username"]).exists():
            raise CommandError("Username already exists.")
        if not is_address(options["controller_address"]):
            raise CommandError("Controller address is invalid.")
        role = Role.objects.filter(code=Role.Code.ADMIN).first()
        if role is None:
            raise CommandError("Run seed_roles before bootstrapping the platform Admin.")
        password = options.get("password")
        if not password:
            password = getpass("Platform Admin password: ")
            password_confirm = getpass("Confirm password: ")
            if password != password_confirm:
                raise CommandError("Passwords do not match.")
        department, _ = Department.objects.get_or_create(code=options["department"], defaults={"name": options["department"].title()})
        user = User.objects.create_user(
            username=options["username"],
            email=options["email"],
            password=password,
            department=department,
            is_staff=True,
            is_superuser=True,
        )
        Profile.objects.create(user=user, employee_id=options["employee_id"])
        controller = to_checksum_address(options["controller_address"])
        did = f"did:ethr:{settings.CHAIN_ID}:{controller}"
        identity = DecentralizedIdentity.objects.create(user=user, did=did, controller_address=controller, state=DecentralizedIdentity.State.INVITED)
        IdentityKey.objects.create(identity=identity, version=1, controller_address=controller, active_from=identity.created_at)
        UserRole.objects.create(user=user, role=role, scope_department=None, granted_by=user)
        row = TransactionService().submit(
            contract_name="IdentityRegistry",
            function_name="registerIdentity",
            args=[Web3.keccak(text=did), controller],
            operation="IDENTITY_REGISTER",
            idempotency_key=f"identity-register:{identity.id}:v1",
            actor_did="bootstrap-governance",
            related_object_type="DecentralizedIdentity",
            related_object_id=identity.id,
        )
        self.stdout.write(self.style.SUCCESS(f"Created platform Admin {user.username}; transaction {row.tx_hash} submitted."))
