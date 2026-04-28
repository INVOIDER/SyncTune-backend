from .base import BaseMusicService
from integrations.oauth.client import get_spotify_oauth


class SpotifyAPIError(Exception):
    def __init__(self, status_code, message):
        self.status_code = status_code
        self.message = message
        super().__init__(message)


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
        if not resp.ok:
            raise SpotifyAPIError(resp.status_code, self._get_error_message(resp))

        try:
            return resp.json()
        except ValueError as exc:
            raise SpotifyAPIError(resp.status_code, "Spotify returned a non-JSON response.") from exc

    def _get_error_message(self, response):
        try:
            payload = response.json()
        except ValueError:
            return response.text or response.reason

        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                return error.get("message") or str(error)
            if error:
                return str(error)
            return payload.get("message") or str(payload)

        return str(payload)
