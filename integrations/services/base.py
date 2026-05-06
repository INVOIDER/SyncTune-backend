class BaseMusicService:
    provider_code = None

    def get_authorization_url(self):
        raise NotImplementedError

    def fetch_token(self, code):
        raise NotImplementedError

    def get_user_profile(self, token):
        raise NotImplementedError

    def list_playlists(self, token, user_id=None):
        raise NotImplementedError

    def get_playlist_tracks(self, token, playlist_id, user_id=None):
        raise NotImplementedError

    def search_tracks(self, token, query, page=0):
        raise NotImplementedError

    def create_playlist(self, token, title, visibility="private", user_id=None):
        raise NotImplementedError

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
        raise NotImplementedError

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
        raise NotImplementedError
