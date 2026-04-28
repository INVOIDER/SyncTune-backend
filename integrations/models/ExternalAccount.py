import uuid

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from .MusicProvider import MusicProvider


class ExternalAccount(models.Model):
    STATUS_CHOICES = [
        ("active", "active"),
        ("need_reauth", "need_reauth"),
        ("error", "error"),
        ("revoked", "revoked"),
        ("disabled", "disabled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    provider = models.ForeignKey(MusicProvider, on_delete=models.RESTRICT)
    external_user_id = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255, blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    access_token_encrypted = models.BinaryField(null=True, blank=True)
    refresh_token_encrypted = models.BinaryField(null=True, blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)

    scopes = ArrayField(models.TextField(), default=list, blank=True)
    metadata = models.JSONField(default=dict)

    last_reauthorized_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "external_accounts"
        unique_together = ("user", "provider", "external_user_id")

    def __str__(self):
        return f"{self.provider.code}:{self.external_user_id}"
