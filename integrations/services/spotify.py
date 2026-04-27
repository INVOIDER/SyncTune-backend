from .base import BaseMusicService
from integrations.oauth.client import get_spotify_oauth


class SpotifyService(BaseMusicService):
    provider_code = "spotify"

    AUTH_URL = "https://accounts.spotify.com/authorize"
    TOKEN_URL = "https://accounts.spotify.com/api/token"
    USER_URL = "https://api.spotify.com/v1/me"

    def get_authorization_url(self):
        oauth = get_spotify_oauth()
        uri, state = oauth.create_authorization_url(self.AUTH_URL)
        return uri, state

    def fetch_token(self, code):
        oauth = get_spotify_oauth()
        return oauth.fetch_token(self.TOKEN_URL, code=code)

    def get_user_profile(self, token):
        oauth = get_spotify_oauth(token=token)
        resp = oauth.get(self.USER_URL)
        return resp.json()