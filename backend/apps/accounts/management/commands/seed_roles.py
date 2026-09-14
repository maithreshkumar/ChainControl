from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Permission, Role


ROLE_PERMISSIONS = {
    Role.Code.ADMIN: {
        "identity.create", "identity.view", "identity.view_all", "identity.revoke",
        "role.assign", "role.revoke", "asset.create", "asset.mint", "asset.view",
        "asset.view_all", "asset.assign", "asset.transfer", "transfer.approve",
        "transfer.view_all", "audit.view", "security.view", "blockchain.view", "blockchain.health",
    },
    Role.Code.VALIDATOR: {
        "identity.view", "identity.view_all", "identity.validate",
        "asset.view", "asset.view_all", "asset.activate",
        "audit.view", "blockchain.view",
    },
    Role.Code.MANAGER: {
        "identity.view", "asset.view", "asset.transfer", "transfer.approve",
        "transfer.view_all", "audit.view", "blockchain.view",
    },
    Role.Code.AUDITOR: {
        "identity.view_all", "asset.view_all", "transfer.view_all", "audit.view",
        "security.view", "blockchain.view", "blockchain.health",
    },
    Role.Code.USER: {"identity.view", "asset.view", "asset.mint", "asset.transfer"},
}


class Command(BaseCommand):
    help = "Create or reconcile the visible platform roles and their granular permissions."

    @transaction.atomic
    def handle(self, *args, **options):
        all_codes = sorted(set().union(*ROLE_PERMISSIONS.values()))
        permissions = {
            code: Permission.objects.update_or_create(code=code, defaults={"description": code.replace(".", " ").title()})[0]
            for code in all_codes
        }
        for role_code, codes in ROLE_PERMISSIONS.items():
            role, _ = Role.objects.update_or_create(code=role_code, defaults={"name": Role.Code(role_code).label})
            role.permissions.set([permissions[code] for code in sorted(codes)])
            self.stdout.write(self.style.SUCCESS(f"Seeded {role_code} ({len(codes)} permissions)"))
