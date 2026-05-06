from django.utils import timezone

from integrations.services import get_music_service

from .accounts import get_account_access_token
from .library import LibraryWriter
from .matching import TrackMatcher
from ..models import MappingCandidate, SyncJob, SyncJobItem, SyncRule


class SyncExecutor:
    def __init__(self):
        self.library = LibraryWriter()
        self.matcher = TrackMatcher()

    def run_rule(self, rule, trigger=SyncJob.Trigger.MANUAL):
        job = SyncJob.objects.create(rule=rule, trigger=trigger, status=SyncJob.Status.PENDING)

        try:
            self._run(rule, job)
        except Exception as exc:
            job.status = SyncJob.Status.FAILED
            job.error_message = str(exc)
            job.finished_at = timezone.now()
            job.save(update_fields=["status", "error_message", "finished_at", "updated_at"])

        return job

    def _run(self, rule, job):
        if rule.direction != SyncRule.Direction.ONE_WAY:
            raise ValueError("Only one-way synchronization is implemented for now.")

        job.status = SyncJob.Status.RUNNING
        job.started_at = timezone.now()
        job.save(update_fields=["status", "started_at", "updated_at"])

        source_service = get_music_service(rule.source_account.provider.code)
        target_service = get_music_service(rule.target_account.provider.code)
        source_token = get_account_access_token(rule.source_account)
        target_token = get_account_access_token(rule.target_account)

        source_cached_track_count = rule.source_playlist.track_count
        target_cached_track_count = rule.target_playlist.track_count

        source_tracks = source_service.get_playlist_tracks(
            source_token,
            rule.source_playlist.external_playlist_id,
            user_id=rule.source_playlist.owner_external_id,
        )
        target_tracks = target_service.get_playlist_tracks(
            target_token,
            rule.target_playlist.external_playlist_id,
            user_id=rule.target_playlist.owner_external_id,
        )

        self.library.save_playlist_tracks(rule.source_playlist, source_tracks)
        target_external_tracks = self.library.save_playlist_tracks(rule.target_playlist, target_tracks)

        job.metadata = self._build_job_metadata(
            rule=rule,
            source_cached_track_count=source_cached_track_count,
            target_cached_track_count=target_cached_track_count,
            source_tracks=source_tracks,
            target_tracks=target_tracks,
        )
        job.total_tracks = len(source_tracks)
        job.save(update_fields=["metadata", "total_tracks", "updated_at"])

        for source_track_data in source_tracks:
            if not source_track_data.get("external_track_id"):
                continue

            source_external_track = self.library.upsert_external_track(rule.source_account.provider, source_track_data)
            existing_target = self._find_existing_target(source_track_data, target_tracks, target_external_tracks)
            if existing_target:
                job.skipped_tracks += 1
                self._create_item(
                    job=job,
                    source_track=source_external_track,
                    target_track=existing_target,
                    action=SyncJobItem.Action.NOOP,
                    status=SyncJobItem.Status.SKIPPED,
                    match_score=1.0,
                    match_method="already_present",
                )
                job.save(update_fields=["skipped_tracks", "updated_at"])
                continue

            candidate = self.matcher.find_best_match(source_track_data, target_service, target_token)
            if not candidate or candidate["score"] < self.matcher.MIN_ACCEPT_SCORE:
                self._handle_unmatched_track(rule, job, source_external_track, candidate)
                continue

            target_track_data = candidate["track"]
            target_external_track = self.library.upsert_external_track(rule.target_account.provider, target_track_data)

            try:
                result = target_service.add_track_to_playlist(
                    target_token,
                    rule.target_playlist.external_playlist_id,
                    target_track_data["external_track_id"],
                    album_id=target_track_data.get("album_id") or target_track_data.get("external_album_id"),
                    revision=self._playlist_revision(rule.target_playlist),
                    user_id=rule.target_playlist.owner_external_id,
                )
                self._update_target_playlist_snapshot(rule, result)
            except Exception as exc:
                job.failed_tracks += 1
                self._create_item(
                    job=job,
                    source_track=source_external_track,
                    target_track=target_external_track,
                    action=SyncJobItem.Action.ADD,
                    status=SyncJobItem.Status.FAILED,
                    match_score=candidate["score"],
                    match_method=candidate["method"],
                    error_message=str(exc),
                )
                job.save(update_fields=["failed_tracks", "updated_at"])
                continue

            job.matched_tracks += 1
            job.added_tracks += 1
            self._create_item(
                job=job,
                source_track=source_external_track,
                target_track=target_external_track,
                action=SyncJobItem.Action.ADD,
                status=SyncJobItem.Status.SUCCESS,
                match_score=candidate["score"],
                match_method=candidate["method"],
            )
            job.save(update_fields=["matched_tracks", "added_tracks", "updated_at"])

        unresolved_items = job.items.filter(
            status__in=[SyncJobItem.Status.CONFLICT, SyncJobItem.Status.MISSING]
        ).exists()
        job.status = SyncJob.Status.PARTIAL if job.failed_tracks or unresolved_items else SyncJob.Status.SUCCESS
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "finished_at", "updated_at"])

        rule.last_run_at = job.finished_at
        rule.save(update_fields=["last_run_at", "updated_at"])

    def _find_existing_target(self, source_track_data, target_tracks, target_external_tracks):
        for target_track_data, target_external_track in zip(target_tracks, target_external_tracks):
            if self.matcher.same_track(source_track_data, target_track_data):
                return target_external_track
        return None

    def _handle_unmatched_track(self, rule, job, source_external_track, candidate):
        target_external_track = None
        action = SyncJobItem.Action.SKIP
        item_status = SyncJobItem.Status.SKIPPED
        match_score = None
        match_method = None

        if candidate:
            target_external_track = self.library.upsert_external_track(rule.target_account.provider, candidate["track"])
            match_score = candidate["score"]
            match_method = candidate["method"]
            self._save_mapping_candidate(rule, source_external_track, target_external_track, candidate)

        should_create_conflict = (
            rule.conflict_policy == SyncRule.ConflictPolicy.MANUAL
            or rule.missing_track_policy == SyncRule.MissingTrackPolicy.CREATE_CONFLICT
        )

        if should_create_conflict:
            action = SyncJobItem.Action.CONFLICT
            item_status = SyncJobItem.Status.CONFLICT if candidate else SyncJobItem.Status.MISSING
        else:
            job.skipped_tracks += 1

        self._create_item(
            job=job,
            source_track=source_external_track,
            target_track=target_external_track,
            action=action,
            status=item_status,
            match_score=match_score,
            match_method=match_method,
        )
        job.save(update_fields=["skipped_tracks", "updated_at"])

    def _save_mapping_candidate(self, rule, source_external_track, target_external_track, candidate):
        MappingCandidate.objects.update_or_create(
            user=rule.user,
            source_track=source_external_track,
            target_track=target_external_track,
            defaults={
                "score": candidate["score"],
                "method": candidate["method"],
                "status": MappingCandidate.Status.CANDIDATE,
                "metadata": candidate,
            },
        )

    def _create_item(
        self,
        job,
        source_track,
        target_track,
        action,
        status,
        match_score=None,
        match_method=None,
        error_message=None,
    ):
        return SyncJobItem.objects.create(
            job=job,
            source_track=source_track,
            target_track=target_track,
            action=action,
            status=status,
            match_score=match_score,
            match_method=match_method,
            error_message=error_message,
        )

    def _build_job_metadata(
        self,
        rule,
        source_cached_track_count,
        target_cached_track_count,
        source_tracks,
        target_tracks,
    ):
        return {
            "source": {
                "provider": rule.source_account.provider.code,
                "playlist_id": str(rule.source_playlist_id),
                "external_playlist_id": rule.source_playlist.external_playlist_id,
                "owner_external_id": rule.source_playlist.owner_external_id,
                "cached_track_count_before_run": source_cached_track_count,
                "fetched_track_count": len(source_tracks),
            },
            "target": {
                "provider": rule.target_account.provider.code,
                "playlist_id": str(rule.target_playlist_id),
                "external_playlist_id": rule.target_playlist.external_playlist_id,
                "owner_external_id": rule.target_playlist.owner_external_id,
                "cached_track_count_before_run": target_cached_track_count,
                "fetched_track_count": len(target_tracks),
            },
        }

    def _playlist_revision(self, playlist):
        if not playlist.snapshot_id:
            return None
        try:
            return int(playlist.snapshot_id)
        except ValueError:
            return None

    def _update_target_playlist_snapshot(self, rule, result):
        snapshot_id = result.get("snapshot_id") if isinstance(result, dict) else None
        if not snapshot_id:
            return

        rule.target_playlist.snapshot_id = snapshot_id
        rule.target_playlist.save(update_fields=["snapshot_id", "updated_at"])
