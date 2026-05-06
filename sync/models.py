import uuid

from django.conf import settings
from django.db import models

from integrations.models import ExternalAccount, MusicProvider


class TimestampedUUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Playlist(TimestampedUUIDModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sync_playlists")
    external_account = models.ForeignKey(ExternalAccount, on_delete=models.CASCADE, related_name="playlists")
    provider = models.ForeignKey(MusicProvider, on_delete=models.RESTRICT, related_name="playlists")
    external_playlist_id = models.CharField(max_length=255)
    owner_external_id = models.CharField(max_length=255, blank=True, null=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    is_public = models.BooleanField(blank=True, null=True)
    track_count = models.PositiveIntegerField(default=0)
    snapshot_id = models.CharField(max_length=255, blank=True, null=True)
    last_fetched_at = models.DateTimeField(blank=True, null=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        db_table = "playlists"
        constraints = [
            models.UniqueConstraint(
                fields=["external_account", "external_playlist_id"],
                name="uq_playlist_account_external_id",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "provider"], name="idx_playlists_user_provider"),
            models.Index(fields=["external_playlist_id"], name="idx_playlists_external_id"),
        ]

    def __str__(self):
        return f"{self.provider.code}:{self.name}"


class Track(TimestampedUUIDModel):
    title = models.CharField(max_length=500)
    normalized_title = models.CharField(max_length=500)
    artists = models.JSONField(default=list)
    normalized_artists = models.CharField(max_length=1000, blank=True)
    album = models.CharField(max_length=500, blank=True, null=True)
    duration_ms = models.PositiveIntegerField(blank=True, null=True)
    isrc = models.CharField(max_length=32, blank=True, null=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        db_table = "tracks"
        indexes = [
            models.Index(fields=["isrc"], name="idx_tracks_isrc"),
            models.Index(fields=["normalized_title"], name="idx_tracks_norm_title"),
        ]

    def __str__(self):
        return self.title


class ExternalTrack(TimestampedUUIDModel):
    provider = models.ForeignKey(MusicProvider, on_delete=models.RESTRICT, related_name="external_tracks")
    track = models.ForeignKey(Track, on_delete=models.SET_NULL, blank=True, null=True, related_name="external_tracks")
    external_track_id = models.CharField(max_length=255)
    external_album_id = models.CharField(max_length=255, blank=True, null=True)
    title = models.CharField(max_length=500)
    normalized_title = models.CharField(max_length=500)
    artists = models.JSONField(default=list)
    normalized_artists = models.CharField(max_length=1000, blank=True)
    album = models.CharField(max_length=500, blank=True, null=True)
    duration_ms = models.PositiveIntegerField(blank=True, null=True)
    isrc = models.CharField(max_length=32, blank=True, null=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        db_table = "external_tracks"
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "external_track_id"],
                name="uq_external_track_provider_id",
            ),
        ]
        indexes = [
            models.Index(fields=["provider", "isrc"], name="idx_ext_tracks_provider_isrc"),
            models.Index(fields=["normalized_title"], name="idx_ext_tracks_norm_title"),
        ]

    def __str__(self):
        return f"{self.provider.code}:{self.title}"


class PlaylistTrack(TimestampedUUIDModel):
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE, related_name="playlist_tracks")
    external_track = models.ForeignKey(ExternalTrack, on_delete=models.CASCADE, related_name="playlist_entries")
    position = models.PositiveIntegerField()
    added_at = models.DateTimeField(blank=True, null=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        db_table = "playlist_tracks"
        indexes = [
            models.Index(fields=["playlist", "position"], name="idx_playlist_tracks_position"),
        ]

    def __str__(self):
        return f"{self.playlist_id}:{self.position}"


class SyncRule(TimestampedUUIDModel):
    class Direction(models.TextChoices):
        ONE_WAY = "one_way", "one_way"
        TWO_WAY = "two_way", "two_way"

    class Mode(models.TextChoices):
        APPEND_ONLY = "append_only", "append_only"
        MIRROR = "mirror", "mirror"

    class ConflictPolicy(models.TextChoices):
        AUTO = "auto", "auto"
        MANUAL = "manual", "manual"
        SKIP = "skip", "skip"

    class MissingTrackPolicy(models.TextChoices):
        SKIP = "skip", "skip"
        CREATE_CONFLICT = "create_conflict", "create_conflict"

    class ScheduleType(models.TextChoices):
        MANUAL = "manual", "manual"
        INTERVAL = "interval", "interval"
        CRON = "cron", "cron"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sync_rules")
    name = models.CharField(max_length=255)
    source_account = models.ForeignKey(
        ExternalAccount,
        on_delete=models.CASCADE,
        related_name="source_sync_rules",
    )
    target_account = models.ForeignKey(
        ExternalAccount,
        on_delete=models.CASCADE,
        related_name="target_sync_rules",
    )
    source_playlist = models.ForeignKey(
        Playlist,
        on_delete=models.CASCADE,
        related_name="source_sync_rules",
    )
    target_playlist = models.ForeignKey(
        Playlist,
        on_delete=models.CASCADE,
        related_name="target_sync_rules",
    )
    direction = models.CharField(max_length=20, choices=Direction.choices, default=Direction.ONE_WAY)
    mode = models.CharField(max_length=20, choices=Mode.choices, default=Mode.APPEND_ONLY)
    conflict_policy = models.CharField(max_length=20, choices=ConflictPolicy.choices, default=ConflictPolicy.MANUAL)
    missing_track_policy = models.CharField(
        max_length=30,
        choices=MissingTrackPolicy.choices,
        default=MissingTrackPolicy.CREATE_CONFLICT,
    )
    schedule_type = models.CharField(max_length=20, choices=ScheduleType.choices, default=ScheduleType.MANUAL)
    schedule_value = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    last_run_at = models.DateTimeField(blank=True, null=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        db_table = "sync_rules"
        indexes = [
            models.Index(fields=["user", "is_active"], name="idx_sync_rules_user_active"),
        ]

    def __str__(self):
        return self.name


class SyncJob(TimestampedUUIDModel):
    class Trigger(models.TextChoices):
        MANUAL = "manual", "manual"
        SCHEDULED = "scheduled", "scheduled"
        RETRY = "retry", "retry"

    class Status(models.TextChoices):
        PENDING = "pending", "pending"
        RUNNING = "running", "running"
        SUCCESS = "success", "success"
        PARTIAL = "partial", "partial"
        FAILED = "failed", "failed"
        CANCELLED = "cancelled", "cancelled"

    rule = models.ForeignKey(SyncRule, on_delete=models.CASCADE, related_name="jobs")
    trigger = models.CharField(max_length=20, choices=Trigger.choices, default=Trigger.MANUAL)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    started_at = models.DateTimeField(blank=True, null=True)
    finished_at = models.DateTimeField(blank=True, null=True)
    total_tracks = models.PositiveIntegerField(default=0)
    matched_tracks = models.PositiveIntegerField(default=0)
    added_tracks = models.PositiveIntegerField(default=0)
    skipped_tracks = models.PositiveIntegerField(default=0)
    failed_tracks = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True, null=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        db_table = "sync_jobs"
        indexes = [
            models.Index(fields=["rule", "status"], name="idx_sync_jobs_rule_status"),
            models.Index(fields=["created_at"], name="idx_sync_jobs_created_at"),
        ]

    def __str__(self):
        return f"{self.rule_id}:{self.status}"


class SyncJobItem(TimestampedUUIDModel):
    class Action(models.TextChoices):
        ADD = "add", "add"
        REMOVE = "remove", "remove"
        SKIP = "skip", "skip"
        NOOP = "noop", "noop"
        CONFLICT = "conflict", "conflict"

    class Status(models.TextChoices):
        PENDING = "pending", "pending"
        SUCCESS = "success", "success"
        FAILED = "failed", "failed"
        SKIPPED = "skipped", "skipped"
        CONFLICT = "conflict", "conflict"
        MISSING = "missing", "missing"

    job = models.ForeignKey(SyncJob, on_delete=models.CASCADE, related_name="items")
    source_track = models.ForeignKey(
        ExternalTrack,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="source_sync_items",
    )
    target_track = models.ForeignKey(
        ExternalTrack,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="target_sync_items",
    )
    action = models.CharField(max_length=20, choices=Action.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    match_score = models.FloatField(blank=True, null=True)
    match_method = models.CharField(max_length=50, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        db_table = "sync_job_items"
        indexes = [
            models.Index(fields=["job", "status"], name="idx_sync_job_items_status"),
        ]

    def __str__(self):
        return f"{self.job_id}:{self.action}:{self.status}"


class MappingCandidate(TimestampedUUIDModel):
    class Status(models.TextChoices):
        CANDIDATE = "candidate", "candidate"
        CONFIRMED = "confirmed", "confirmed"
        REJECTED = "rejected", "rejected"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mapping_candidates")
    source_track = models.ForeignKey(
        ExternalTrack,
        on_delete=models.CASCADE,
        related_name="mapping_candidates_from",
    )
    target_track = models.ForeignKey(
        ExternalTrack,
        on_delete=models.CASCADE,
        related_name="mapping_candidates_to",
    )
    score = models.FloatField()
    method = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CANDIDATE)
    confirmed_by_user = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict)

    class Meta:
        db_table = "mapping_candidates"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "source_track", "target_track"],
                name="uq_mapping_candidate_user_pair",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "status"], name="idx_mapping_candidates_status"),
        ]

    def __str__(self):
        return f"{self.source_track_id}->{self.target_track_id}:{self.score}"
