import base64
import hashlib

from cryptography.fernet import Fernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def _build_fernet():
    raw_key = getattr(settings, "MUSIC_TOKEN_ENCRYPTION_KEY", None) or settings.SECRET_KEY
    if not raw_key:
        raise ImproperlyConfigured("Set SECRET_KEY or MUSIC_TOKEN_ENCRYPTION_KEY before storing provider tokens.")

    key_bytes = raw_key.encode()
    try:
        return Fernet(key_bytes)
    except ValueError:
        digest = hashlib.sha256(key_bytes).digest()
        return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_token(value):
    if not value:
        return None
    return _build_fernet().encrypt(value.encode())


def decrypt_token(value):
    if not value:
        return None
    return _build_fernet().decrypt(bytes(value)).decode()
