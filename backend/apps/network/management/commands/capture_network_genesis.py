from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User
from apps.network.services import NetworkAdmissionError, register_canonical_genesis


class Command(BaseCommand):
    help = "Register and hash the exact existing generated Besu genesis without replacing it."

    def add_arguments(self, parser):
        parser.add_argument("--actor", help="Optional Django superuser username recorded as the operator.")

    def handle(self, *args, **options):
        actor = None
        if options.get("actor"):
            actor = User.objects.filter(username=options["actor"], is_superuser=True).first()
            if actor is None:
                raise CommandError("The named actor is not a Django superuser.")
        try:
            configuration = register_canonical_genesis(actor=actor)
        except NetworkAdmissionError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"Canonical chain {configuration.chain_id} genesis SHA-256: {configuration.genesis_hash}"))
