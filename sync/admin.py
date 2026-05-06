from django.contrib import admin

from .models import (
    ExternalTrack,
    MappingCandidate,
    Playlist,
    PlaylistTrack,
    SyncJob,
    SyncJobItem,
    SyncRule,
    Track,
)


@admin.register(Playlist)
class PlaylistAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "provider", "external_account", "track_count", "last_fetched_at")
    list_filter = ("provider", "is_public")
    search_fields = ("name", "external_playlist_id", "user__email")


@admin.register(Track)
class TrackAdmin(admin.ModelAdmin):
    list_display = ("title", "album", "duration_ms", "isrc")
    search_fields = ("title", "album", "isrc", "normalized_artists")


@admin.register(ExternalTrack)
class ExternalTrackAdmin(admin.ModelAdmin):
    list_display = ("title", "provider", "album", "duration_ms", "isrc")
    list_filter = ("provider",)
    search_fields = ("title", "album", "isrc", "external_track_id", "normalized_artists")


@admin.register(PlaylistTrack)
class PlaylistTrackAdmin(admin.ModelAdmin):
    list_display = ("playlist", "external_track", "position")
    search_fields = ("playlist__name", "external_track__title")


@admin.register(SyncRule)
class SyncRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "source_playlist", "target_playlist", "is_active", "last_run_at")
    list_filter = ("is_active", "direction", "mode", "conflict_policy")
    search_fields = ("name", "user__email", "source_playlist__name", "target_playlist__name")


@admin.register(SyncJob)
class SyncJobAdmin(admin.ModelAdmin):
    list_display = ("rule", "trigger", "status", "total_tracks", "added_tracks", "failed_tracks", "created_at")
    list_filter = ("status", "trigger")
    search_fields = ("rule__name",)


@admin.register(SyncJobItem)
class SyncJobItemAdmin(admin.ModelAdmin):
    list_display = ("job", "action", "status", "source_track", "target_track", "match_score")
    list_filter = ("action", "status", "match_method")
    search_fields = ("source_track__title", "target_track__title", "error_message")


@admin.register(MappingCandidate)
class MappingCandidateAdmin(admin.ModelAdmin):
    list_display = ("user", "source_track", "target_track", "score", "method", "status")
    list_filter = ("status", "method", "confirmed_by_user")
    search_fields = ("source_track__title", "target_track__title", "user__email")
