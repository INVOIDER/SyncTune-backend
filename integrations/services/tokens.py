from datetime import datetime, timedelta, timezone as datetime_timezone

from django.utils import timezone

from integrations.security import decrypt_token, encrypt_token
from integrations.services.spotify import SpotifyAPIError, SpotifyService


TOKEN_REFRESH_MARGIN = timedelta(minutes=2)


class ExternalAccountTokenError(Exception):
    pass


def get_account_access_token(account):
    if account.status != "active":
        raise ExternalAccountTokenError("External account is not active.")

    if account.provider.code == SpotifyService.provider_code and _should_refresh_token(account):
        _refresh_spotify_account_token(account)

    token = decrypt_token(account.access_token_encrypted)
    if not token:
        raise ExternalAccountTokenError("External account has no access token.")

    return token


def _should_refresh_token(account):
    if account.token_expires_at is None:
        return bool(account.refresh_token_encrypted)

    return account.token_expires_at <= timezone.now() + TOKEN_REFRESH_MARGIN


def _refresh_spotify_account_token(account):
    refresh_token = decrypt_token(account.refresh_token_encrypted)
    if not refresh_token:
        account.status = "need_reauth"
        account.save(update_fields=["status", "updated_at"])
        raise ExternalAccountTokenError("Spotify account has no refresh token. Reconnect this provider account.")

    try:
        token = SpotifyService().refresh_access_token(refresh_token)
    except SpotifyAPIError as exc:
        if exc.status_code in {400, 401, 403}:
            account.status = "need_reauth"
            account.save(update_fields=["status", "updated_at"])
        raise ExternalAccountTokenError(f"Failed to refresh Spotify access token: {exc.message}") from exc

    account.access_token_encrypted = encrypt_token(token["access_token"])

    if token.get("refresh_token"):
        account.refresh_token_encrypted = encrypt_token(token["refresh_token"])

    expires_at = _get_token_expires_at(token)
    if expires_at:
        account.token_expires_at = expires_at

    scope = token.get("scope")
    if isinstance(scope, str):
        account.scopes = scope.split()
    elif scope:
        account.scopes = list(scope)

    account.status = "active"
    account.save(
        update_fields=[
            "access_token_encrypted",
            "refresh_token_encrypted",
            "token_expires_at",
            "scopes",
            "status",
            "updated_at",
        ]
    )


def _get_token_expires_at(token):
    if token.get("expires_in"):
        return timezone.now() + timedelta(seconds=int(token["expires_in"]))

    if token.get("expires_at"):
        return datetime.fromtimestamp(float(token["expires_at"]), tz=datetime_timezone.utc)

    return None
