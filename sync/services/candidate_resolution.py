from django.db.models import Max
from django.utils import timezone

from integrations.services import get_music_service

from .accounts import get_account_access_token
from ..models import MappingCandidate, PlaylistTrack, SyncJob, SyncJobItem, SyncRule


class MappingCandidateResolutionError(Exception):
    pass


class MappingCandidateResolutionService:
    def confirm(self, user, candidate, rule):
        self._validate_candidate_for_rule(user, candidate, rule)

        job = SyncJob.objects.create(
            rule=rule,
            trigger=SyncJob.Trigger.MANUAL,
            status=SyncJob.Status.RUNNING,
            started_at=timezone.now(),
            total_tracks=1,
        )

        if self._target_playlist_contains_candidate(rule, candidate):
            self._mark_candidate_confirmed(candidate)
            self._finish_job_as_skipped(job, candidate)
            return job

        target_service = get_music_service(rule.target_account.provider.code)
        target_token = get_account_access_token(rule.target_account)

        try:
            result = target_service.add_track_to_playlist(
                target_token,
                rule.target_playlist.external_playlist_id,
                candidate.target_track.external_track_id,
                album_id=candidate.target_track.external_album_id,
                revision=self._playlist_revision(rule.target_playlist),
                user_id=rule.target_playlist.owner_external_id,
            )
            self._update_target_playlist_snapshot(rule, result)
            self._add_candidate_to_local_playlist(rule, candidate)
        except Exception as exc:
            self._finish_job_as_failed(job, candidate, exc)
            raise MappingCandidateResolutionError(str(exc)) from exc

        self._mark_candidate_confirmed(candidate)
        self._finish_job_as_success(job, candidate)
        return job

    def reject(self, user, candidate):
        if candidate.user_id != user.id:
            raise MappingCandidateResolutionError("Mapping candidate does not belong to the current user.")

        candidate.status = MappingCandidate.Status.REJECTED
        candidate.confirmed_by_user = False
        candidate.save(update_fields=["status", "confirmed_by_user", "updated_at"])
        return candidate

    def _validate_candidate_for_rule(self, user, candidate, rule):
        if candidate.user_id != user.id:
            raise MappingCandidateResolutionError("Mapping candidate does not belong to the current user.")

        if rule.user_id != user.id:
            raise MappingCandidateResolutionError("Sync rule does not belong to the current user.")

        if rule.direction != SyncRule.Direction.ONE_WAY:
            raise MappingCandidateResolutionError("Only one-way sync rules can be resolved manually for now.")

        if candidate.source_track.provider_id != rule.source_account.provider_id:
            raise MappingCandidateResolutionError("Candidate source provider does not match the sync rule source.")

        if candidate.target_track.provider_id != rule.target_account.provider_id:
            raise MappingCandidateResolutionError("Candidate target provider does not match the sync rule target.")

        if candidate.status == MappingCandidate.Status.REJECTED:
            raise MappingCandidateResolutionError("Rejected mapping candidate cannot be confirmed.")

    def _target_playlist_contains_candidate(self, rule, candidate):
        return PlaylistTrack.objects.filter(
            playlist=rule.target_playlist,
            external_track=candidate.target_track,
        ).exists()

    def _add_candidate_to_local_playlist(self, rule, candidate):
        max_position = (
            PlaylistTrack.objects.filter(playlist=rule.target_playlist)
            .aggregate(max_position=Max("position"))
            .get("max_position")
            or 0
        )
        PlaylistTrack.objects.update_or_create(
            playlist=rule.target_playlist,
            external_track=candidate.target_track,
            defaults={
                "position": max_position + 1,
                "metadata": {
                    "source": "manual_mapping_confirmation",
                    "mapping_candidate_id": str(candidate.id),
                },
            },
        )

        rule.target_playlist.track_count = PlaylistTrack.objects.filter(playlist=rule.target_playlist).count()
        rule.target_playlist.last_fetched_at = timezone.now()
        rule.target_playlist.save(update_fields=["track_count", "last_fetched_at", "updated_at"])

    def _mark_candidate_confirmed(self, candidate):
        candidate.status = MappingCandidate.Status.CONFIRMED
        candidate.confirmed_by_user = True
        candidate.save(update_fields=["status", "confirmed_by_user", "updated_at"])

    def _finish_job_as_skipped(self, job, candidate):
        SyncJobItem.objects.create(
            job=job,
            source_track=candidate.source_track,
            target_track=candidate.target_track,
            action=SyncJobItem.Action.NOOP,
            status=SyncJobItem.Status.SKIPPED,
            match_score=candidate.score,
            match_method=f"manual_{candidate.method}",
        )
        job.status = SyncJob.Status.SUCCESS
        job.skipped_tracks = 1
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "skipped_tracks", "finished_at", "updated_at"])

    def _finish_job_as_success(self, job, candidate):
        SyncJobItem.objects.create(
            job=job,
            source_track=candidate.source_track,
            target_track=candidate.target_track,
            action=SyncJobItem.Action.ADD,
            status=SyncJobItem.Status.SUCCESS,
            match_score=candidate.score,
            match_method=f"manual_{candidate.method}",
        )
        job.status = SyncJob.Status.SUCCESS
        job.matched_tracks = 1
        job.added_tracks = 1
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "matched_tracks", "added_tracks", "finished_at", "updated_at"])

    def _finish_job_as_failed(self, job, candidate, exc):
        SyncJobItem.objects.create(
            job=job,
            source_track=candidate.source_track,
            target_track=candidate.target_track,
            action=SyncJobItem.Action.ADD,
            status=SyncJobItem.Status.FAILED,
            match_score=candidate.score,
            match_method=f"manual_{candidate.method}",
            error_message=str(exc),
        )
        job.status = SyncJob.Status.FAILED
        job.failed_tracks = 1
        job.error_message = str(exc)
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "failed_tracks", "error_message", "finished_at", "updated_at"])

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
