from django.utils import timezone

from .normalization import normalize_artists, normalize_text
from ..models import ExternalTrack, Playlist, PlaylistTrack, Track


class LibraryWriter:
    def upsert_playlist(self, user, external_account, playlist_data):
        playlist, _ = Playlist.objects.update_or_create(
            external_account=external_account,
            external_playlist_id=playlist_data["external_playlist_id"],
            defaults={
                "user": user,
                "provider": external_account.provider,
                "owner_external_id": playlist_data.get("owner_id"),
                "name": playlist_data.get("name") or "Untitled playlist",
                "description": playlist_data.get("description"),
                "is_public": playlist_data.get("is_public"),
                "track_count": playlist_data.get("track_count") or 0,
                "snapshot_id": playlist_data.get("snapshot_id"),
                "last_fetched_at": timezone.now(),
                "metadata": playlist_data.get("metadata") or {},
            },
        )
        return playlist

    def upsert_external_track(self, provider, track_data):
        artists = track_data.get("artists")
        if artists is None:
            artist = track_data.get("artist")
            artists = [artist] if artist else []

        normalized_title = normalize_text(track_data.get("title"))
        normalized_artists = normalize_artists(artists)
        canonical_track = self._get_or_create_track(track_data, artists, normalized_title, normalized_artists)

        external_track, _ = ExternalTrack.objects.update_or_create(
            provider=provider,
            external_track_id=track_data["external_track_id"],
            defaults={
                "track": canonical_track,
                "external_album_id": track_data.get("external_album_id") or track_data.get("album_id"),
                "title": track_data.get("title") or "Untitled track",
                "normalized_title": normalized_title,
                "artists": artists,
                "normalized_artists": normalized_artists,
                "album": track_data.get("album"),
                "duration_ms": track_data.get("duration_ms"),
                "isrc": track_data.get("isrc"),
                "metadata": track_data.get("metadata") or {},
            },
        )
        return external_track

    def upsert_playlist_track(self, playlist, external_track, track_data):
        position = track_data.get("position") or 0
        playlist_track, _ = PlaylistTrack.objects.update_or_create(
            playlist=playlist,
            position=position,
            defaults={
                "external_track": external_track,
                "metadata": track_data.get("metadata") or {},
            },
        )
        return playlist_track

    def save_playlist_tracks(self, playlist, track_data_list):
        saved_tracks = []
        for index, track_data in enumerate(track_data_list, start=1):
            if not track_data.get("external_track_id"):
                continue

            track_data.setdefault("position", index)
            external_track = self.upsert_external_track(playlist.provider, track_data)
            self.upsert_playlist_track(playlist, external_track, track_data)
            saved_tracks.append(external_track)

        playlist.track_count = len(saved_tracks)
        playlist.last_fetched_at = timezone.now()
        playlist.save(update_fields=["track_count", "last_fetched_at", "updated_at"])
        return saved_tracks

    def _get_or_create_track(self, track_data, artists, normalized_title, normalized_artists):
        isrc = track_data.get("isrc")
        if isrc:
            existing = Track.objects.filter(isrc__iexact=isrc).first()
            if existing:
                return existing

        existing = Track.objects.filter(
            normalized_title=normalized_title,
            normalized_artists=normalized_artists,
            duration_ms=track_data.get("duration_ms"),
        ).first()
        if existing:
            return existing

        return Track.objects.create(
            title=track_data.get("title") or "Untitled track",
            normalized_title=normalized_title,
            artists=artists,
            normalized_artists=normalized_artists,
            album=track_data.get("album"),
            duration_ms=track_data.get("duration_ms"),
            isrc=isrc,
            metadata=track_data.get("metadata") or {},
        )
