from django.contrib import admin
from integrations.models import ExternalAccount, MusicProvider


@admin.register(MusicProvider)
class MusicProviderAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "supports_oauth", "is_active")
    search_fields = ("code", "name")
    list_filter = ("supports_oauth", "is_active")


@admin.register(ExternalAccount)
class ExternalAccountAdmin(admin.ModelAdmin):
    list_display = ("user", "provider", "external_user_id", "display_name", "status", "token_expires_at")
    search_fields = ("external_user_id", "display_name", "user__email", "provider__code")
    list_filter = ("provider", "status")
    exclude = ("access_token_encrypted", "refresh_token_encrypted")
    readonly_fields = ("created_at", "updated_at", "last_reauthorized_at")
