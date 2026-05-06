import spotipy
from spotipy.exceptions import SpotifyException

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

    def get_authorization_url(self):
        oauth = get_spotify_oauth()
        uri, state = oauth.create_authorization_url(self.AUTH_URL)
        return uri, state

    def fetch_token(self, code):
        oauth = get_spotify_oauth()
        return oauth.fetch_token(self.TOKEN_URL, code=code)

    def refresh_access_token(self, refresh_token):
        oauth = get_spotify_oauth()
        try:
            return oauth.refresh_token(self.TOKEN_URL, refresh_token=refresh_token)
        except Exception as exc:
            raise SpotifyAPIError(400, str(exc)) from exc

    def get_user_profile(self, token):
        return self._call_spotify(token, lambda client: client.current_user())

    def list_playlists(self, token, user_id=None):
        items = self._collect_items(
            token,
            lambda client: client.current_user_playlists(),
        )
        return [self._playlist_to_dto(item) for item in items]

    def get_playlist_tracks(self, token, playlist_id, user_id=None):
        items = self._collect_items(
            token,
            lambda client: client.playlist_items(
                playlist_id,
                fields="items(track),next",
                limit=100,
            ),
        )

        tracks = []
        for position, item in enumerate(items, start=1):
            track = item.get("track") if isinstance(item, dict) else None
            if not track or track.get("type") != "track":
                continue
            tracks.append(self._track_to_dto(track, position=position))
        return tracks

    def search_tracks(self, token, query, page=0):
        payload = self._call_spotify(
            token,
            lambda client: client.search(q=query, type="track", limit=10, offset=page * 10),
        )
        tracks = payload.get("tracks", {}).get("items", [])
        return [self._track_to_dto(track) for track in tracks]

    def create_playlist(self, token, title, visibility="private", user_id=None):
        if not user_id:
            user_id = self.get_user_profile(token)["id"]

        data = self._call_spotify(
            token,
            lambda client: client.user_playlist_create(
                user=user_id,
                name=title,
                public=visibility == "public",
            ),
        )
        return self._playlist_to_dto(data)

    def add_track_to_playlist(
        self,
        token,
        playlist_id,
        track_id,
        album_id=None,
        position=None,
        revision=None,
        user_id=None,
    ):
        data = self._call_spotify(
            token,
            lambda client: client.playlist_add_items(
                playlist_id=playlist_id,
                items=[self._track_uri(track_id)],
                position=position,
            ),
        )
        return {
            "external_playlist_id": str(playlist_id),
            "snapshot_id": data.get("snapshot_id"),
            "metadata": data,
        }

    def remove_track_from_playlist(
        self,
        token,
        playlist_id,
        track_id,
        album_id=None,
        position=None,
        revision=None,
        user_id=None,
    ):
        data = self._call_spotify(
            token,
            lambda client: client.playlist_remove_all_occurrences_of_items(
                playlist_id=playlist_id,
                items=[self._track_uri(track_id)],
                snapshot_id=revision,
            ),
        )
        return {
            "external_playlist_id": str(playlist_id),
            "snapshot_id": data.get("snapshot_id"),
            "metadata": data,
        }

    def _call_spotify(self, token, callback):
        client = self._build_client(token)
        try:
            return callback(client)
        except SpotifyException as exc:
            raise SpotifyAPIError(
                self._get_exception_status(exc),
                self._get_exception_message(exc),
            ) from exc

    def _collect_items(self, token, first_page_callback):
        client = self._build_client(token)
        items = []

        try:
            page = first_page_callback(client)
            while page:
                items.extend(page.get("items", []))
                page = client.next(page) if page.get("next") else None
        except SpotifyException as exc:
            raise SpotifyAPIError(
                self._get_exception_status(exc),
                self._get_exception_message(exc),
            ) from exc

        return items

    def _build_client(self, token):
        return spotipy.Spotify(auth=self._extract_access_token(token))

    def _extract_access_token(self, token):
        if isinstance(token, dict):
            return token["access_token"]

        value = str(token).strip()
        for prefix in ("Bearer ", "OAuth "):
            if value.startswith(prefix):
                return value[len(prefix):].strip()
        return value

    def _playlist_to_dto(self, playlist):
        owner = playlist.get("owner") or {}
        tracks = playlist.get("tracks") or {}

        return {
            "external_playlist_id": str(playlist.get("id") or ""),
            "owner_id": str(owner.get("id") or ""),
            "name": playlist.get("name"),
            "description": playlist.get("description"),
            "is_public": playlist.get("public"),
            "track_count": tracks.get("total") or 0,
            "snapshot_id": playlist.get("snapshot_id"),
            "metadata": playlist,
        }

    def _track_to_dto(self, track, position=None):
        album = track.get("album") or {}
        artists = track.get("artists") or []
        artist_names = [artist.get("name") for artist in artists if artist.get("name")]

        return {
            "external_track_id": str(track.get("id") or ""),
            "external_album_id": str(album.get("id") or ""),
            "album_id": str(album.get("id") or ""),
            "title": track.get("name"),
            "artist": ", ".join(artist_names),
            "artists": artist_names,
            "album": album.get("name"),
            "duration_ms": track.get("duration_ms"),
            "isrc": (track.get("external_ids") or {}).get("isrc"),
            "position": position,
            "metadata": track,
        }

    def _track_uri(self, track_id):
        value = str(track_id)
        if value.startswith("spotify:track:"):
            return value
        return f"spotify:track:{value}"

    def _get_exception_status(self, exc):
        return getattr(exc, "http_status", None) or 400

    def _get_exception_message(self, exc):
        return getattr(exc, "msg", None) or getattr(exc, "reason", None) or str(exc)
