import secrets
from datetime import timedelta

from django import forms
from django.contrib import admin, messages
from django.contrib.auth.hashers import make_password
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Max
from django.shortcuts import redirect, render
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone

from .models import BlockchainNode, EnrollmentToken, NetworkConfiguration, NodePeerSnapshot, ValidatorGovernanceOperation
from .services import (
    NetworkAdmissionError,
    approve_node,
    current_validator_set,
    initiate_validator_change,
    refresh_validator_operation,
    register_canonical_genesis,
    reject_node,
    revoke_node,
)


class SuperuserNetworkAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        return bool(request.user.is_superuser)

    def has_view_permission(self, request, obj=None):
        return bool(request.user.is_superuser)

    def has_add_permission(self, request):
        return bool(request.user.is_superuser)

    def has_change_permission(self, request, obj=None):
        return bool(request.user.is_superuser)

    def has_delete_permission(self, request, obj=None):
        return False


class EnrollmentTokenAdminForm(forms.ModelForm):
    enrollment_code = forms.CharField(
        required=False,
        min_length=16,
        widget=forms.PasswordInput(render_value=False),
        help_text="Leave blank to generate a strong single-use code. It is shown once after saving.",
    )

    class Meta:
        model = EnrollmentToken
        fields = ("label", "expires_at", "enrollment_code")

    def clean(self):
        cleaned = super().clean()
        code = cleaned.get("enrollment_code") or f"JOIN-{secrets.token_urlsafe(24)}"
        self.generated_code = code
        self.instance.token_digest = make_password(code)
        return cleaned


@admin.register(EnrollmentToken)
class EnrollmentTokenAdmin(SuperuserNetworkAdmin):
    form = EnrollmentTokenAdminForm
    list_display = ("label", "expires_at", "used_at", "usable")
    list_filter = ("expires_at", "used_at")
    search_fields = ("label",)
    readonly_fields = ("created_by", "used_at", "created_at", "updated_at")

    def get_urls(self):
        custom_urls = [
            path(
                "<path:object_id>/reveal/",
                self.admin_site.admin_view(self.reveal_code_view),
                name="network_enrollmenttoken_reveal",
            ),
        ]
        return custom_urls + super().get_urls()

    def get_changeform_initial_data(self, request):
        return {"expires_at": timezone.now() + timedelta(hours=24)}

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        if not change:
            request.session[f"network_enrollment_code:{obj.pk}"] = form.generated_code

    def response_add(self, request, obj, post_url_continue=None):
        return redirect(reverse("admin:network_enrollmenttoken_reveal", args=[obj.pk]))

    def reveal_code_view(self, request, object_id):
        token = self.get_object(request, object_id)
        if token is None:
            self.message_user(request, "Enrollment token not found.", level=messages.ERROR)
            return redirect(reverse("admin:network_enrollmenttoken_changelist"))
        code = request.session.pop(f"network_enrollment_code:{token.pk}", None)
        if not code:
            self.message_user(
                request,
                "That enrollment code has already been displayed. Create a new token if it was not saved.",
                level=messages.WARNING,
            )
            return redirect(reverse("admin:network_enrollmenttoken_changelist"))
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Enrollment code created",
            "token": token,
            "enrollment_code": code,
            "changelist_url": reverse("admin:network_enrollmenttoken_changelist"),
            "add_url": reverse("admin:network_enrollmenttoken_add"),
        }
        return TemplateResponse(request, "admin/network/enrollmenttoken/reveal.html", context)


@admin.register(BlockchainNode)
class BlockchainNodeAdmin(SuperuserNetworkAdmin):
    change_form_template = "admin/network/blockchainnode/change_form.html"
    list_display = ("node_name", "node_uuid", "owner", "node_type", "status", "latest_block", "sync_percentage", "peer_count", "last_seen")
    list_filter = ("status", "node_type", "is_validator", "requested_validator")
    search_fields = ("node_name", "node_uuid", "owner__username", "node_address", "enode", "host_or_overlay_address")
    readonly_fields = tuple(field.name for field in BlockchainNode._meta.fields)
    actions = ("approve_selected", "reject_selected", "revoke_selected", "promote_selected", "remove_validator_selected")

    def response_change(self, request, obj):
        if "_approve_node" in request.POST:
            try:
                approve_node(obj, request.user)
                self.message_user(
                    request,
                    f"Yes selected: {obj.node_name} was approved and Besu permissioning was verified.",
                    messages.SUCCESS,
                )
            except NetworkAdmissionError as exc:
                self.message_user(request, f"Approval failed: {exc}", messages.ERROR)
            return redirect(reverse("admin:network_blockchainnode_change", args=[obj.pk]))
        if "_reject_node" in request.POST:
            try:
                reject_node(obj, request.user, "Rejected by Django superuser from the node review page.")
                self.message_user(request, f"No selected: {obj.node_name} was rejected.", messages.SUCCESS)
            except NetworkAdmissionError as exc:
                self.message_user(request, f"Rejection failed: {exc}", messages.ERROR)
            return redirect(reverse("admin:network_blockchainnode_change", args=[obj.pk]))
        return super().response_change(request, obj)

    @admin.action(description="Approve selected pending nodes and propagate Besu permissioning")
    def approve_selected(self, request, queryset):
        for node in queryset:
            try:
                approve_node(node, request.user)
                self.message_user(request, f"Approved {node.node_name}; Besu allowlist propagation verified.", messages.SUCCESS)
            except NetworkAdmissionError as exc:
                self.message_user(request, f"Could not approve {node.node_name}: {exc}", messages.ERROR)

    @admin.action(description="Reject selected pending nodes")
    def reject_selected(self, request, queryset):
        for node in queryset:
            try:
                reject_node(node, request.user, "Rejected by Django superuser.")
            except NetworkAdmissionError as exc:
                self.message_user(request, f"Could not reject {node.node_name}: {exc}", messages.ERROR)

    @admin.action(description="Revoke selected nodes and remove Besu permissioning")
    def revoke_selected(self, request, queryset):
        for node in queryset:
            try:
                revoke_node(node, request.user, "Revoked by Django superuser.")
                self.message_user(request, f"Revoked {node.node_name}; Besu allowlist removal verified.", messages.SUCCESS)
            except NetworkAdmissionError as exc:
                self.message_user(request, f"Could not revoke {node.node_name}: {exc}", messages.ERROR)

    @admin.action(description="Initiate real QBFT validator promotion")
    def promote_selected(self, request, queryset):
        for node in queryset:
            try:
                operation = initiate_validator_change(node, request.user, add=True)
                self.message_user(request, f"Promotion for {node.node_name}: {operation.status}.", messages.SUCCESS)
            except NetworkAdmissionError as exc:
                self.message_user(request, f"Could not promote {node.node_name}: {exc}", messages.ERROR)

    @admin.action(description="Initiate real QBFT validator removal")
    def remove_validator_selected(self, request, queryset):
        for node in queryset:
            try:
                operation = initiate_validator_change(node, request.user, add=False)
                self.message_user(request, f"Validator removal for {node.node_name}: {operation.status}.", messages.SUCCESS)
            except NetworkAdmissionError as exc:
                self.message_user(request, f"Could not remove {node.node_name}: {exc}", messages.ERROR)


@admin.register(NetworkConfiguration)
class NetworkConfigurationAdmin(SuperuserNetworkAdmin):
    list_display = ("network_name", "chain_id", "genesis_hash", "permissioning_revision", "updated_at")
    readonly_fields = ("genesis_hash", "genesis_json", "genesis_text", "permissioning_revision", "updated_at", "updated_by")
    actions = ("capture_existing_genesis",)

    def has_add_permission(self, request):
        return request.user.is_superuser and not NetworkConfiguration.objects.exists()

    @admin.action(description="Register exact existing generated genesis (never replace it)")
    def capture_existing_genesis(self, request, queryset):
        try:
            configuration = register_canonical_genesis(actor=request.user)
            self.message_user(request, f"Registered canonical genesis SHA-256 {configuration.genesis_hash}.", messages.SUCCESS)
        except NetworkAdmissionError as exc:
            self.message_user(request, str(exc), messages.ERROR)


@admin.register(ValidatorGovernanceOperation)
class ValidatorGovernanceOperationAdmin(SuperuserNetworkAdmin):
    list_display = ("node", "action", "status", "candidate_address", "requested_by", "created_at", "completed_at")
    list_filter = ("action", "status")
    search_fields = ("node__node_name", "node__node_uuid", "candidate_address")
    readonly_fields = tuple(field.name for field in ValidatorGovernanceOperation._meta.fields)
    actions = ("refresh_selected",)

    def has_add_permission(self, request):
        return False

    @admin.action(description="Refresh selected operations from the actual QBFT validator set")
    def refresh_selected(self, request, queryset):
        for operation in queryset:
            refreshed = refresh_validator_operation(operation)
            self.message_user(request, f"{operation.node.node_name}: {refreshed.status}.", messages.SUCCESS)


def network_dashboard(request):
    if not request.user.is_superuser:
        raise PermissionDenied
    nodes = BlockchainNode.objects.select_related("owner").all()
    status_counts = {row["status"]: row["total"] for row in nodes.values("status").annotate(total=Count("id"))}
    type_counts = {row["node_type"]: row["total"] for row in nodes.values("node_type").annotate(total=Count("id"))}
    try:
        validators = current_validator_set()
        consensus = "AVAILABLE" if validators else "NO VALIDATORS REPORTED"
    except NetworkAdmissionError as exc:
        validators = []
        consensus = f"UNAVAILABLE: {exc}"
    enode_nodes = {node.enode.lower(): node for node in nodes}
    topology_edges = []
    for snapshot in NodePeerSnapshot.objects.select_related("reporter"):
        peer = enode_nodes.get(snapshot.peer_enode.lower())
        if peer:
            topology_edges.append({"source": snapshot.reporter, "target": peer, "observed_at": snapshot.observed_at})
    context = admin.site.each_context(request)
    context.update(
        title="Blockchain Network",
        nodes=nodes,
        total_nodes=nodes.count(),
        online_nodes=status_counts.get(BlockchainNode.Status.ONLINE, 0),
        offline_nodes=status_counts.get(BlockchainNode.Status.OFFLINE, 0),
        pending_nodes=status_counts.get(BlockchainNode.Status.PENDING, 0),
        full_nodes=type_counts.get(BlockchainNode.NodeType.FULL_NODE, 0),
        validator_nodes=len(validators),
        validator_addresses=validators,
        latest_block=nodes.aggregate(value=Max("latest_block"))["value"],
        consensus=consensus,
        topology_edges=topology_edges,
    )
    return render(request, "admin/network/dashboard.html", context)
