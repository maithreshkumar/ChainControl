import os
import re
import uuid
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.assets.models import Asset, AssetVersion
from apps.assets.storage import retrieve_and_verify
from apps.audit.services import record_audit


class Command(BaseCommand):
    help = "Decrypt one authorized digital-asset version to an explicitly controlled local file."

    def add_arguments(self, parser):
        parser.add_argument("asset_id", help="Unique Asset UUID (an identifier, never a key)")
        parser.add_argument("--actor", required=True, help="Django username authorizing the operation")
        parser.add_argument("--reason", required=True, help="Administrative reason recorded in the audit trail")
        parser.add_argument("--output", required=True, help="Exact plaintext output file path")
        parser.add_argument("--asset-version", type=int, help="Asset version number; defaults to the latest")
        parser.add_argument("--request-id", help="External request UUID; generated when omitted")
        parser.add_argument("--force", action="store_true", help="Explicitly replace an existing regular output file")
        parser.add_argument("--cleanup", action="store_true", help="Explicitly remove the plaintext after integrity verification")

    def handle(self, *args, **options):
        actor = self._authorized_actor(options["actor"])
        request_id = self._request_id(options.get("request_id"))
        raw_asset_id = options["asset_id"]
        reason = options["reason"].strip()
        output = Path(os.path.abspath(os.path.expanduser(options["output"])))
        version = None
        output_written = False

        if not reason:
            raise CommandError("--reason cannot be empty.")

        try:
            asset_id = uuid.UUID(raw_asset_id)
            asset = Asset.objects.get(id=asset_id)
            if asset.asset_type != Asset.AssetType.DIGITAL_ASSET:
                raise CommandError("Only DIGITAL_ASSET records contain decryptable content.")
            versions = AssetVersion.objects.filter(asset=asset)
            version = versions.filter(version=options["asset_version"]).first() if options.get("asset_version") else versions.order_by("-version").first()
            if version is None:
                raise CommandError("The requested asset version does not exist.")
            self._validate_metadata(version)
            plaintext = retrieve_and_verify(version)
            self._write_private_file(output, plaintext, force=options["force"])
            output_written = True

            details = {
                "reason": reason,
                "result": "DECRYPTED_AND_CLEANED" if options["cleanup"] else "DECRYPTED",
                "source_object": version.object_key,
                "request_id": str(request_id),
                "asset_version": version.version,
                "content_hash_verified": True,
            }
            if options["cleanup"]:
                output.unlink()
                output_written = False
            record_audit(
                action="ADMIN_DECRYPT", object_type="Asset", object_id=asset.id, actor=actor,
                outcome="SUCCESS", correlation_id=request_id, details=details,
            )
            if options["cleanup"]:
                self.stdout.write(self.style.SUCCESS("Asset decrypted, authenticated, hash-verified, and explicitly cleaned up."))
            else:
                self.stdout.write(self.style.WARNING(f"Plaintext written with restricted permissions to: {output}"))
                self.stdout.write("Delete this file securely when the authorized work is complete.")
        except Exception as exc:
            if output_written and output.exists():
                try:
                    output.unlink()
                except OSError:
                    pass
            record_audit(
                action="ADMIN_DECRYPT", object_type="Asset", object_id=raw_asset_id, actor=actor,
                outcome="FAILED", correlation_id=request_id,
                details={
                    "reason": reason,
                    "result": "FAILED",
                    "source_object": version.object_key if version else "",
                    "request_id": str(request_id),
                    "error_type": getattr(exc, "code", exc.__class__.__name__),
                },
            )
            if isinstance(exc, CommandError):
                raise
            raise CommandError(str(exc)) from exc

    @staticmethod
    def _authorized_actor(username):
        try:
            actor = get_user_model().objects.get(username=username, is_active=True)
        except get_user_model().DoesNotExist as exc:
            raise CommandError("The active administrative actor was not found.") from exc
        if not actor.is_superuser and not actor.has_platform_permission("asset.decrypt"):
            raise CommandError("The actor is not authorized to decrypt assets.")
        return actor

    @staticmethod
    def _request_id(value):
        try:
            return uuid.UUID(value) if value else uuid.uuid4()
        except ValueError as exc:
            raise CommandError("--request-id must be a UUID.") from exc

    @staticmethod
    def _validate_metadata(version):
        expected_prefix = f"assets/{version.asset_id}/versions/"
        if not version.object_key.startswith(expected_prefix) or not version.object_key.endswith(".enc"):
            raise CommandError("Asset storage metadata contains an invalid object key.")
        if not re.fullmatch(r"[0-9a-f]{64}", version.content_hash or ""):
            raise CommandError("Asset storage metadata contains an invalid content hash.")
        if not all((version.content_nonce, version.wrap_nonce, version.wrapped_key)):
            raise CommandError("Asset encryption metadata is incomplete.")

    @staticmethod
    def _write_private_file(path, plaintext, *, force):
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and (path.is_dir() or path.is_symlink()):
            raise CommandError("The output target must be a regular file, not a directory or symbolic link.")
        flags = os.O_WRONLY | os.O_CREAT | (os.O_TRUNC if force else os.O_EXCL)
        try:
            descriptor = os.open(path, flags, 0o600)
        except FileExistsError as exc:
            raise CommandError("The output file already exists. Use --force only after checking it.") from exc
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(plaintext)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(path, 0o600)
        except Exception:
            try:
                path.unlink()
            except OSError:
                pass
            raise
