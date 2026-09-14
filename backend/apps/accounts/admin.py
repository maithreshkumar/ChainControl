from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.hashers import make_password
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from eth_account import Account

from apps.identities.models import DecentralizedIdentity, IdentityKey

from .models import Department, Invitation, Profile, User, UserRole, WalletProvision

admin.site.register(Department)


class ProfileInline(admin.StackedInline):
    model = Profile
    extra = 0
    max_num = 1
    fields = ("employee_id", "clearance")
    verbose_name_plural = "Employee profile"


class UserRoleInline(admin.TabularInline):
    model = UserRole
    fk_name = "user"
    extra = 0
    fields = ("role", "scope_department", "active", "granted_by", "granted_at", "revoked_at")
    readonly_fields = ("granted_by", "granted_at")
    verbose_name_plural = "Platform roles"


@admin.register(User)
class PlatformUserAdmin(UserAdmin):
    inlines = (ProfileInline, UserRoleInline)
    list_display = ("username", "email", "department", "employee_id", "roles_summary", "invited_by_summary", "is_active")
    list_filter = ("is_active", "is_staff", "is_superuser", "department", "role_assignments__role")
    search_fields = ("username", "email", "first_name", "last_name", "profile__employee_id")
    list_select_related = ("department", "profile")
    filter_horizontal = ()
    readonly_fields = (
        "last_login",
        "date_joined",
        "invited_by_summary",
        "roles_summary",
        "permissions_summary",
        "wallet_status",
    )
    fieldsets = (
        ("Sign-in", {"fields": ("username", "password")}),
        ("Person and department", {"fields": ("first_name", "last_name", "email", "department")}),
        (
            "Access overview",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "invited_by_summary",
                    "roles_summary",
                    "permissions_summary",
                    "wallet_status",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined"), "classes": ("collapse",)}),
    )
    add_fieldsets = (
        (
            "Create account",
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "email",
                    "first_name",
                    "last_name",
                    "department",
                    "password1",
                    "password2",
                    "is_active",
                    "is_staff",
                ),
            },
        ),
    )

    @admin.display(description="Employee ID")
    def employee_id(self, obj):
        try:
            return obj.profile.employee_id
        except ObjectDoesNotExist:
            return "Not assigned"

    @admin.display(description="Platform roles")
    def roles_summary(self, obj):
        roles = [
            f"{assignment.role.code} ({assignment.scope_department.code if assignment.scope_department else 'all departments'})"
            for assignment in obj.role_assignments.filter(active=True).select_related("role", "scope_department")
        ]
        return ", ".join(roles) or "No active platform role"

    @admin.display(description="Effective permissions")
    def permissions_summary(self, obj):
        permissions = obj.role_assignments.filter(active=True).values_list("role__permissions__code", flat=True).distinct()
        return ", ".join(sorted(permission for permission in permissions if permission)) or "No platform permissions"

    @admin.display(description="Invited by")
    def invited_by_summary(self, obj):
        invitation = Invitation.objects.filter(
            Q(email__iexact=obj.email) | Q(username__iexact=obj.username)
        ).select_related("created_by").order_by("-accepted_at", "-created_at").first()
        if invitation is None:
            return "Directly created; no invitation record"
        invited_by = invitation.created_by.get_username()
        invited_at = timezone.localtime(invitation.created_at).strftime("%Y-%m-%d %I:%M %p IST")
        return f"{invited_by} on {invited_at}"

    @admin.display(description="Controller wallet")
    def wallet_status(self, obj):
        try:
            provision = obj.wallet_provision
        except ObjectDoesNotExist:
            add_url = reverse("admin:accounts_walletprovision_add")
            return format_html('Not issued · <a href="{}?user={}">Issue wallet</a>', add_url, obj.pk)
        change_url = reverse("admin:accounts_walletprovision_change", args=[provision.pk])
        state = "Claimed" if provision.claimed_at else "Issued, not claimed"
        return format_html('{} · <a href="{}">Manage wallet</a>', state, change_url)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, UserRole) and instance.granted_by_id is None:
                instance.granted_by = request.user
            instance.save()
        for deleted in formset.deleted_objects:
            deleted.delete()
        formset.save_m2m()


class ProfileAdminForm(forms.ModelForm):
    username = forms.CharField(max_length=150, help_text="The username used to sign in to ChainControl.")
    email = forms.EmailField()
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    department = forms.ModelChoiceField(queryset=Department.objects.all(), required=False)
    new_password = forms.CharField(
        required=False,
        min_length=12,
        widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}),
        help_text="Leave blank to keep the current password.",
    )
    confirm_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}),
    )

    class Meta:
        model = Profile
        fields = ("user", "username", "email", "first_name", "last_name", "department", "employee_id", "clearance")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            person = self.instance.user
            self.fields["username"].initial = person.username
            self.fields["email"].initial = person.email
            self.fields["first_name"].initial = person.first_name
            self.fields["last_name"].initial = person.last_name
            self.fields["department"].initial = person.department
            if "user" in self.fields:
                self.fields["user"].queryset = User.objects.filter(Q(profile__isnull=True) | Q(pk=person.pk))
        elif "user" in self.fields:
            self.fields["user"].queryset = User.objects.filter(profile__isnull=True)

    def clean(self):
        cleaned = super().clean()
        person = cleaned.get("user") or (self.instance.user if self.instance.pk else None)
        username = cleaned.get("username", "").strip()
        email = cleaned.get("email", "").strip()
        password = cleaned.get("new_password", "")
        confirmation = cleaned.get("confirm_password", "")
        if person and username and User.objects.filter(username__iexact=username).exclude(pk=person.pk).exists():
            self.add_error("username", "This username is already in use.")
        if person and email and User.objects.filter(email__iexact=email).exclude(pk=person.pk).exists():
            self.add_error("email", "This email address is already in use.")
        if password != confirmation:
            self.add_error("confirm_password", "The two password fields do not match.")
        if person and password:
            try:
                validate_password(password, user=person)
            except ValidationError as exc:
                self.add_error("new_password", exc)
        return cleaned

    def apply_person_fields(self, profile):
        person = self.cleaned_data.get("user") or profile.user
        person.username = self.cleaned_data["username"].strip()
        person.email = self.cleaned_data["email"].strip()
        person.first_name = self.cleaned_data.get("first_name", "").strip()
        person.last_name = self.cleaned_data.get("last_name", "").strip()
        person.department = self.cleaned_data.get("department")
        if self.cleaned_data.get("new_password"):
            person.set_password(self.cleaned_data["new_password"])
        profile.user = person
        return person

    @transaction.atomic
    def save(self, commit=True):
        profile = super().save(commit=False)
        person = self.apply_person_fields(profile)
        if commit:
            person.save()
            profile.save()
        return profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    form = ProfileAdminForm
    change_form_template = "admin/accounts/profile/change_form.html"
    list_display = ("username", "employee_id", "email", "department", "clearance", "updated_at")
    list_filter = ("clearance", "user__department")
    list_select_related = ("user", "user__department")
    search_fields = ("user__username", "user__email", "user__first_name", "user__last_name", "employee_id")
    fields = (
        "user",
        "username",
        "email",
        "first_name",
        "last_name",
        "department",
        "employee_id",
        "clearance",
        "new_password",
        "confirm_password",
    )

    def get_readonly_fields(self, request, obj=None):
        return ("user",) if obj else ()

    def save_model(self, request, obj, form, change):
        person = form.apply_person_fields(obj)
        person.save()
        super().save_model(request, obj, form, change)

    @admin.display(ordering="user__username", description="Username")
    def username(self, obj):
        return obj.user.username

    @admin.display(ordering="user__email", description="Email")
    def email(self, obj):
        return obj.user.email

    @admin.display(ordering="user__department", description="Department")
    def department(self, obj):
        return obj.user.department or "Not assigned"


class WalletProvisionAdminForm(forms.ModelForm):
    generate_controller_key = forms.BooleanField(
        label="Generate a new controller key",
        required=False,
        help_text="Use this only for an account that does not yet have a DID identity.",
    )
    controller_private_key = forms.CharField(
        label="Controller private key",
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text="For an existing DID, enter its matching controller key to issue or reissue the wallet.",
    )
    wallet_access_code = forms.CharField(
        label="Wallet access code",
        min_length=12,
        widget=forms.PasswordInput(render_value=False),
        help_text="Give this code to the account holder through an approved channel. It is not recoverable from Django.",
    )

    class Meta:
        model = WalletProvision
        fields = ("user",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "user" in self.fields:
            self.fields["user"].queryset = User.objects.filter(
                is_staff=False,
                is_superuser=False,
                wallet_provision__isnull=True,
            ).order_by("username")

    def clean(self):
        cleaned = super().clean()
        user = cleaned.get("user") or getattr(self.instance, "user", None)
        private_key = cleaned.get("controller_private_key", "").strip()
        access_code = cleaned.get("wallet_access_code", "")
        generate_key = cleaned.get("generate_controller_key", False)
        if not user or not access_code:
            return cleaned
        try:
            identity = user.identity
        except ObjectDoesNotExist:
            identity = None
        if generate_key and identity is not None:
            raise ValidationError("This account already has a DID. Reissue its existing controller key instead of generating a new one.")
        if generate_key and private_key:
            raise ValidationError("Choose key generation or enter an existing private key, not both.")
        if not generate_key and not private_key:
            raise ValidationError("Generate a new controller key or enter the existing DID controller private key.")
        if generate_key:
            account = Account.create()
        else:
            if identity is None:
                raise ValidationError("This account has no DID. Select Generate a new controller key.")
            try:
                account = Account.from_key(private_key if private_key.startswith("0x") else f"0x{private_key}")
            except (ValueError, TypeError) as exc:
                raise ValidationError("The controller private key is invalid.") from exc
        if identity is not None and account.address.lower() != identity.controller_address.lower():
            raise ValidationError(
                f"This key controls {account.address}, but the account DID requires {identity.controller_address}."
            )
        self._create_identity = identity is None
        self.instance.controller_address = account.address
        self.instance.encrypted_wallet = Account.encrypt(account.key, access_code)
        self.instance.access_code_digest = make_password(access_code)
        self.instance.claimed_at = None
        return cleaned

    @transaction.atomic
    def create_identity_if_needed(self, provision):
        if not getattr(self, "_create_identity", False):
            return
        identity, created = DecentralizedIdentity.objects.get_or_create(
            user=provision.user,
            defaults={
                "did": f"did:ethr:{settings.CHAIN_ID}:{provision.controller_address}",
                "controller_address": provision.controller_address,
                "state": DecentralizedIdentity.State.VALIDATION_PENDING,
            },
        )
        if created:
            IdentityKey.objects.create(
                identity=identity,
                version=1,
                controller_address=provision.controller_address,
                active_from=timezone.now(),
            )

    def save(self, commit=True):
        provision = super().save(commit=commit)
        if commit:
            self.create_identity_if_needed(provision)
        return provision


@admin.register(WalletProvision)
class WalletProvisionAdmin(admin.ModelAdmin):
    form = WalletProvisionAdminForm
    list_display = ("user", "controller_address", "claimed_at", "issued_by", "updated_at")
    search_fields = ("user__username", "user__email", "controller_address")
    readonly_fields = ("controller_address", "claimed_at", "issued_by", "created_at", "updated_at")

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields + (("user",) if obj else ())

    def save_model(self, request, obj, form, change):
        obj.issued_by = request.user
        super().save_model(request, obj, form, change)
        form.create_identity_if_needed(obj)
