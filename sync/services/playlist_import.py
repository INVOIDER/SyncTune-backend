from integrations.services import get_music_service

from .accounts import get_account_access_token
from .library import LibraryWriter


class PlaylistImportService:
    def __init__(self):
        self.library = LibraryWriter()

    def import_account_playlists(self, user, external_account):
        if external_account.user_id != user.id:
            raise ValueError("External account does not belong to the current user.")

        service = get_music_service(external_account.provider.code)
        token = get_account_access_token(external_account)
        playlists = service.list_playlists(token, user_id=external_account.external_user_id)

        return [
            self.library.upsert_playlist(user, external_account, playlist_data)
            for playlist_data in playlists
            if playlist_data.get("external_playlist_id")
        ]

    def import_playlist_tracks(self, playlist):
        service = get_music_service(playlist.provider.code)
        token = get_account_access_token(playlist.external_account)
        track_data_list = service.get_playlist_tracks(
            token,
            playlist.external_playlist_id,
            user_id=playlist.owner_external_id,
        )
        return self.library.save_playlist_tracks(playlist, track_data_list)
