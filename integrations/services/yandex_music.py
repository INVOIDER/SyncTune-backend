import re

from yandex_music import Client
from yandex_music.exceptions import YandexMusicError

from .base import BaseMusicService


class YandexMusicAPIError(Exception):
    def __init__(self, status_code, message):
        self.status_code = status_code
        self.message = message
        super().__init__(message)


class YandexMusicService(BaseMusicService):
    provider_code = "yandex_music"
    WRONG_REVISION_RE = re.compile(r"actual revision:\s*(\d+)", re.IGNORECASE)

    API_BASE_URL = "https://api.music.yandex.net"
    TOKEN_HELP_URL = (
        "https://oauth.yandex.ru/authorize"
        "?response_type=token&client_id=23cabbbdc6cd418abb4b39c32c41195d"
    )

    def get_authorization_url(self):
        return self.TOKEN_HELP_URL

    def fetch_token(self, code):
        raise NotImplementedError("Yandex Music does not provide a Spotify-like OAuth callback for custom apps.")

    def build_client(self, token):
        access_token = self.normalize_token(token)
        try:
            return Client(access_token).init()
        except YandexMusicError as exc:
            raise YandexMusicAPIError(401, str(exc)) from exc

    def get_user_profile(self, token):
        client = self.build_client(token)
        status = self._call_yandex_music(client.account_status)
        account = getattr(status, "account", None)

        external_user_id = getattr(account, "uid", None) or getattr(account, "login", None)
        if not external_user_id:
            raise YandexMusicAPIError(502, "Yandex Music account response has no user id.")

        display_name = (
            getattr(account, "display_name", None)
            or getattr(account, "full_name", None)
            or getattr(account, "login", None)
        )

        return {
            "external_user_id": str(external_user_id),
            "display_name": display_name,
            "metadata": {
                "connection_method": "manual_token",
                "official_oauth_supported": False,
                "api_library": "yandex-music",
                "account": self._to_dict(account),
                "permissions": self._to_dict(getattr(status, "permissions", None)),
                "subscription": self._to_dict(getattr(status, "subscription", None)),
                "default_email": getattr(status, "default_email", None),
            },
        }

    def list_playlists(self, token, user_id=None):
        client = self.build_client(token)
        playlists = self._call_yandex_music(client.users_playlists_list, user_id=user_id)
        return [self._playlist_to_dto(playlist) for playlist in playlists or []]

    def get_playlist_tracks(self, token, playlist_id, user_id=None):
        client = self.build_client(token)
        playlist = self._call_yandex_music(client.users_playlists, playlist_id, user_id=user_id)
        track_items = getattr(playlist, "tracks", None) or []
        return [self._track_short_to_dto(track_item, position) for position, track_item in enumerate(track_items, start=1)]

    def search_tracks(self, token, query, page=0):
        client = self.build_client(token)
        search = self._call_yandex_music(client.search, query, type_="track", page=page)
        tracks = getattr(getattr(search, "tracks", None), "results", None) or []
        return [self._track_to_dto(track) for track in tracks]

    def create_playlist(self, token, title, visibility="private", user_id=None):
        client = self.build_client(token)
        playlist = self._call_yandex_music(
            client.users_playlists_create,
            title,
            visibility=visibility,
            user_id=user_id,
        )
        return self._playlist_to_dto(playlist)

    def add_track_to_playlist(
        self,
        token,
        playlist_id,
        track_id,
        album_id=None,
        position=0,
        revision=None,
        user_id=None,
    ):
        client = self.build_client(token)
        revision = revision or self._get_playlist_revision(client, playlist_id, user_id=user_id)

        try:
            playlist = self._insert_track_to_playlist(
                client,
                playlist_id,
                track_id,
                album_id,
                position=position,
                revision=revision,
                user_id=user_id,
            )
        except YandexMusicAPIError as exc:
            actual_revision = self._actual_revision_from_error(exc)
            if actual_revision is None:
                raise

            playlist = self._insert_track_to_playlist(
                client,
                playlist_id,
                track_id,
                album_id,
                position=position,
                revision=actual_revision,
                user_id=user_id,
            )
        return self._playlist_to_dto(playlist)

    def _insert_track_to_playlist(
        self,
        client,
        playlist_id,
        track_id,
        album_id,
        position=0,
        revision=None,
        user_id=None,
    ):
        return self._call_yandex_music(
            client.users_playlists_insert_track,
            playlist_id,
            track_id,
            album_id,
            at=position,
            revision=revision,
            user_id=user_id,
        )

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
        if position is None:
            raise YandexMusicAPIError(400, "Yandex Music requires track position to remove it from a playlist.")

        client = self.build_client(token)
        revision = revision or self._get_playlist_revision(client, playlist_id, user_id=user_id)

        try:
            playlist = self._delete_track_from_playlist(
                client,
                playlist_id,
                position,
                revision=revision,
                user_id=user_id,
            )
        except YandexMusicAPIError as exc:
            actual_revision = self._actual_revision_from_error(exc)
            if actual_revision is None:
                raise

            playlist = self._delete_track_from_playlist(
                client,
                playlist_id,
                position,
                revision=actual_revision,
                user_id=user_id,
            )
        return self._playlist_to_dto(playlist)

    def _delete_track_from_playlist(self, client, playlist_id, position, revision=None, user_id=None):
        return self._call_yandex_music(
            client.users_playlists_delete_track,
            playlist_id,
            position,
            position + 1,
            revision=revision,
            user_id=user_id,
        )

    def normalize_token(self, token):
        value = token.strip()
        for prefix in ("OAuth ", "Bearer "):
            if value.startswith(prefix):
                return value[len(prefix):].strip()
        return value

    def _call_yandex_music(self, func, *args, **kwargs):
        try:
            return func(*args, **kwargs)
        except YandexMusicError as exc:
            raise YandexMusicAPIError(400, str(exc)) from exc

    def _get_playlist_revision(self, client, playlist_id, user_id=None):
        playlist = self._call_yandex_music(client.users_playlists, playlist_id, user_id=user_id)
        return getattr(playlist, "revision", None) or 1

    def _actual_revision_from_error(self, exc):
        message = str(exc)
        if "wrong-revision" not in message:
            return None

        match = self.WRONG_REVISION_RE.search(message)
        if not match:
            return None

        return int(match.group(1))

    def _playlist_to_dto(self, playlist):
        return {
            "external_playlist_id": str(getattr(playlist, "kind", "")),
            "owner_id": str(getattr(playlist, "uid", "") or ""),
            "name": getattr(playlist, "title", None),
            "description": getattr(playlist, "description", None),
            "is_public": getattr(playlist, "visibility", None) == "public",
            "track_count": getattr(playlist, "track_count", None) or 0,
            "snapshot_id": str(getattr(playlist, "revision", "") or ""),
            "metadata": self._to_dict(playlist),
        }

    def _track_short_to_dto(self, track_item, position):
        track = getattr(track_item, "track", None)
        album_id = getattr(track_item, "album_id", None)
        return self._track_to_dto(track, position=position, album_id=album_id)

    def _track_to_dto(self, track, position=None, album_id=None):
        albums = getattr(track, "albums", None) or []
        first_album = albums[0] if albums else None
        artists = getattr(track, "artists", None) or []
        title = getattr(track, "title", None)
        artist_names = [getattr(artist, "name", None) for artist in artists]
        artist_names = [name for name in artist_names if name]

        return {
            "external_track_id": str(getattr(track, "id", "")),
            "external_album_id": str(album_id or getattr(first_album, "id", "") or ""),
            "album_id": str(album_id or getattr(first_album, "id", "") or ""),
            "title": title,
            "artist": ", ".join(artist_names),
            "artists": artist_names,
            "album": getattr(first_album, "title", None),
            "duration_ms": getattr(track, "duration_ms", None),
            "isrc": None,
            "position": position,
            "metadata": self._to_dict(track),
        }

    def _to_dict(self, value):
        if value is None:
            return None
        if hasattr(value, "to_dict"):
            return value.to_dict()
        return value
