import uuid
from django.db import models
from integrations.models import MusicProvider
from users.models import User


class ExternalAccount(models.Model):
    STATUS_CHOICES = [
        ("active", "active"),
        ("need_reauth", "need_reauth"),
        ("error", "error"),
        ("revoked", "revoked"),
        ("disabled", "disabled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    provider = models.ForeignKey(MusicProvider, on_delete=models.RESTRICT)

    external_user_id = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    access_token_encrypted = models.BinaryField(null=True, blank=True)
    refresh_token_encrypted = models.BinaryField(null=True, blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)

    scopes = models.JSONField(default=list)
    metadata = models.JSONField(default=dict)

    last_reauthorized_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "external_accounts"
        unique_together = ("user", "provider", "external_user_id")