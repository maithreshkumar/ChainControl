import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.blockchain.models import ContractDeployment


class Command(BaseCommand):
    help = "Import Hardhat deployment metadata into the operational database."

    def add_arguments(self, parser):
        parser.add_argument("path", type=Path)

    def handle(self, *args, **options):
        path = options["path"]
        if not path.exists():
            raise CommandError(f"Deployment file not found: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        chain_id = int(payload["chainId"])
        for name, data in payload["contracts"].items():
            ContractDeployment.objects.filter(name=name, chain_id=chain_id, active=True).update(active=False)
            ContractDeployment.objects.update_or_create(
                name=name,
                version=data.get("version", "1.0.0"),
                chain_id=chain_id,
                defaults={
                    "address": data["address"],
                    "abi": data["abi"],
                    "deployment_tx_hash": data["deploymentTxHash"],
                    "deployment_block": data["deploymentBlock"],
                    "active": True,
                },
            )
            self.stdout.write(self.style.SUCCESS(f"Imported {name} at {data['address']}"))

