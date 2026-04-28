
from authlib.integrations.requests_client import OAuth2Session
from django.conf import settings


def get_spotify_oauth(token=None):
    return OAuth2Session(
        client_id=settings.SPOTIFY_CLIENT_ID,
        client_secret=settings.SPOTIFY_CLIENT_SECRET,
        scope="user-read-email playlist-read-private playlist-modify-public playlist-modify-private",
        redirect_uri=settings.SPOTIFY_REDIRECT_URI,
        token=token,
    )
