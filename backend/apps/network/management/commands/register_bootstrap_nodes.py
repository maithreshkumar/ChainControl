import uuid

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.network.models import BlockchainNode
from apps.network.services import NetworkAdmissionError, current_validator_set, load_static_enodes
from apps.network.validation import address_from_public_key, parse_enode


class Command(BaseCommand):
    help = "Register the existing bootstrap validators from the public static-node file. Private keys are never read."

    def handle(self, *args, **options):
        try:
            enodes = load_static_enodes()
            validators = set(current_validator_set())
        except NetworkAdmissionError as exc:
            raise CommandError(str(exc)) from exc
        if not enodes:
            raise CommandError("No existing bootstrap enodes were found.")
        for index, enode in enumerate(enodes, 1):
            normalized, public_key, host, port = parse_enode(enode)
            address = address_from_public_key(public_key)
            is_validator = address.lower() in validators
            node, created = BlockchainNode.objects.update_or_create(
                enode=normalized,
                defaults={
                    "node_uuid": uuid.uuid5(uuid.NAMESPACE_URL, normalized),
                    "node_name": f"Bootstrap Validator {index}",
                    "node_public_key": public_key,
                    "node_address": address,
                    "host_or_overlay_address": host,
                    "p2p_port": port,
                    "rpc_port": 8545,
                    "ws_port": 8546,
                    "node_type": BlockchainNode.NodeType.VALIDATOR if is_validator else BlockchainNode.NodeType.FULL_NODE,
                    "status": BlockchainNode.Status.ONLINE,
                    "is_validator": is_validator,
                    "requested_validator": is_validator,
                    "approved_at": timezone.now(),
                    "joined_at": timezone.now(),
                    "last_seen": timezone.now(),
                    "software_version": "25.7.0",
                },
            )
            self.stdout.write(self.style.SUCCESS(f"{'Created' if created else 'Updated'} {node.node_name}: {node.node_address}"))
