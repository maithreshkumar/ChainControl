from django.contrib import admin

from .models import AuthenticationChallenge, DecentralizedIdentity, IdentityKey


@admin.register(DecentralizedIdentity)
class IdentityAdmin(admin.ModelAdmin):
    list_display = ("did", "user", "state", "controller_address", "key_version")
    readonly_fields = ("registration_tx_hash", "created_at", "updated_at")


admin.site.register(IdentityKey)
admin.site.register(AuthenticationChallenge)

