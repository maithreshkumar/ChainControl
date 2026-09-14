from getpass import getpass

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from eth_account import Account
from eth_utils import is_address, to_checksum_address
from web3 import Web3

from apps.accounts.models import Department, Profile, Role, User, UserRole
from apps.blockchain.transaction_service import TransactionService
from apps.identities.models import DecentralizedIdentity, IdentityKey


class Command(BaseCommand):
    help = "Create the first Validator and register its DID using the governance signer."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--email", required=True)
        parser.add_argument("--employee-id", required=True)
        parser.add_argument("--department", default="GOVERNANCE")
        parser.add_argument("--controller-address", default="")
        parser.add_argument("--password", default="")

    @transaction.atomic
    def handle(self, *args, **options):
        if User.objects.filter(username=options["username"]).exists():
            raise CommandError("Username already exists.")
        role = Role.objects.filter(code=Role.Code.VALIDATOR).first()
        if role is None:
            raise CommandError("Run seed_roles before bootstrapping a Validator.")

        generated_account = None
        controller_address = options["controller_address"]
        if controller_address:
            if not is_address(controller_address):
                raise CommandError("Controller address is invalid.")
            controller = to_checksum_address(controller_address)
        else:
            generated_account = Account.create()
            controller = generated_account.address

        password = options["password"]
        if not password:
            password = getpass("Validator application password: ")
            if password != getpass("Confirm password: "):
                raise CommandError("Passwords do not match.")

        department, _ = Department.objects.get_or_create(
            code=options["department"],
            defaults={"name": options["department"].title()},
        )
        user = User.objects.create_user(
            username=options["username"],
            email=options["email"],
            password=password,
            department=department,
        )
        Profile.objects.create(user=user, employee_id=options["employee_id"])
        did = f"did:ethr:{settings.CHAIN_ID}:{controller}"
        identity = DecentralizedIdentity.objects.create(
            user=user,
            did=did,
            controller_address=controller,
            state=DecentralizedIdentity.State.BLOCKCHAIN_PENDING,
        )
        IdentityKey.objects.create(
            identity=identity,
            version=1,
            controller_address=controller,
            active_from=identity.created_at,
        )
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
        self.stdout.write(self.style.SUCCESS(
            f"Created Validator {user.username} ({controller}); transaction {row.tx_hash} submitted."
        ))
        if generated_account is not None:
            self.stdout.write(self.style.WARNING(
                "ONE-TIME LOCAL WALLET PRIVATE KEY: " + generated_account.key.hex()
            ))
            self.stdout.write(self.style.WARNING(
                "Import this key into ChainControl Wallet, then store the backup securely. It is not saved by Django."
            ))
