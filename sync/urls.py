from django.urls import path

from .views import (
    MappingCandidateConfirmView,
    MappingCandidateListView,
    MappingCandidateRejectView,
    PlaylistImportView,
    PlaylistListView,
    PlaylistTrackListView,
    PlaylistTrackRefreshView,
    SyncJobDetailView,
    SyncJobListView,
    SyncRuleDetailView,
    SyncRuleListCreateView,
    SyncRuleRunView,
)


urlpatterns = [
    path("playlists/", PlaylistListView.as_view(), name="sync-playlist-list"),
    path("playlists/import/", PlaylistImportView.as_view(), name="sync-playlist-import"),
    path("playlists/<uuid:playlist_id>/tracks/", PlaylistTrackListView.as_view(), name="sync-playlist-tracks"),
    path(
        "playlists/<uuid:playlist_id>/tracks/refresh/",
        PlaylistTrackRefreshView.as_view(),
        name="sync-playlist-tracks-refresh",
    ),
    path("rules/", SyncRuleListCreateView.as_view(), name="sync-rule-list"),
    path("rules/<uuid:rule_id>/", SyncRuleDetailView.as_view(), name="sync-rule-detail"),
    path("rules/<uuid:rule_id>/run/", SyncRuleRunView.as_view(), name="sync-rule-run"),
    path("jobs/", SyncJobListView.as_view(), name="sync-job-list"),
    path("jobs/<uuid:job_id>/", SyncJobDetailView.as_view(), name="sync-job-detail"),
    path("mapping-candidates/", MappingCandidateListView.as_view(), name="sync-mapping-candidate-list"),
    path(
        "mapping-candidates/<uuid:candidate_id>/confirm/",
        MappingCandidateConfirmView.as_view(),
        name="sync-mapping-candidate-confirm",
    ),
    path(
        "mapping-candidates/<uuid:candidate_id>/reject/",
        MappingCandidateRejectView.as_view(),
        name="sync-mapping-candidate-reject",
    ),
]
