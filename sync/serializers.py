from rest_framework import serializers

from integrations.models import ExternalAccount
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


class PlaylistSerializer(serializers.ModelSerializer):
    provider = serializers.CharField(source="provider.code", read_only=True)
    external_account_id = serializers.UUIDField(source="external_account.id", read_only=True)

    class Meta:
        model = Playlist
        fields = (
            "id",
            "external_account_id",
            "provider",
            "external_playlist_id",
            "owner_external_id",
            "name",
            "description",
            "is_public",
            "track_count",
            "snapshot_id",
            "last_fetched_at",
            "created_at",
            "updated_at",
        )


class TrackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Track
        fields = ("id", "title", "artists", "album", "duration_ms", "isrc")


class ExternalTrackSerializer(serializers.ModelSerializer):
    provider = serializers.CharField(source="provider.code", read_only=True)

    class Meta:
        model = ExternalTrack
        fields = (
            "id",
            "provider",
            "external_track_id",
            "external_album_id",
            "title",
            "artists",
            "album",
            "duration_ms",
            "isrc",
        )


class PlaylistTrackSerializer(serializers.ModelSerializer):
    external_track = ExternalTrackSerializer(read_only=True)

    class Meta:
        model = PlaylistTrack
        fields = ("id", "position", "external_track", "added_at")


class SyncRuleSerializer(serializers.ModelSerializer):
    source_provider = serializers.CharField(source="source_account.provider.code", read_only=True)
    target_provider = serializers.CharField(source="target_account.provider.code", read_only=True)
    source_playlist_name = serializers.CharField(source="source_playlist.name", read_only=True)
    target_playlist_name = serializers.CharField(source="target_playlist.name", read_only=True)

    class Meta:
        model = SyncRule
        fields = (
            "id",
            "name",
            "source_account",
            "target_account",
            "source_provider",
            "target_provider",
            "source_playlist",
            "target_playlist",
            "source_playlist_name",
            "target_playlist_name",
            "direction",
            "mode",
            "conflict_policy",
            "missing_track_policy",
            "schedule_type",
            "schedule_value",
            "is_active",
            "last_run_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("last_run_at", "created_at", "updated_at")

    def validate(self, attrs):
        request = self.context["request"]
        instance = self.instance

        source_account = attrs.get("source_account") or getattr(instance, "source_account", None)
        target_account = attrs.get("target_account") or getattr(instance, "target_account", None)
        source_playlist = attrs.get("source_playlist") or getattr(instance, "source_playlist", None)
        target_playlist = attrs.get("target_playlist") or getattr(instance, "target_playlist", None)

        for account in (source_account, target_account):
            if account and account.user_id != request.user.id:
                raise serializers.ValidationError("Selected external account does not belong to the current user.")

        for playlist in (source_playlist, target_playlist):
            if playlist and playlist.user_id != request.user.id:
                raise serializers.ValidationError("Selected playlist does not belong to the current user.")

        if source_playlist and source_account and source_playlist.external_account_id != source_account.id:
            raise serializers.ValidationError("Source playlist must belong to the source account.")

        if target_playlist and target_account and target_playlist.external_account_id != target_account.id:
            raise serializers.ValidationError("Target playlist must belong to the target account.")

        if source_account and target_account and source_account.id == target_account.id:
            raise serializers.ValidationError("Source and target accounts must be different.")

        return attrs

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class SyncJobItemSerializer(serializers.ModelSerializer):
    source_track = ExternalTrackSerializer(read_only=True)
    target_track = ExternalTrackSerializer(read_only=True)

    class Meta:
        model = SyncJobItem
        fields = (
            "id",
            "source_track",
            "target_track",
            "action",
            "status",
            "match_score",
            "match_method",
            "error_message",
            "created_at",
        )


class SyncJobSerializer(serializers.ModelSerializer):
    rule_name = serializers.CharField(source="rule.name", read_only=True)

    class Meta:
        model = SyncJob
        fields = (
            "id",
            "rule",
            "rule_name",
            "trigger",
            "status",
            "started_at",
            "finished_at",
            "total_tracks",
            "matched_tracks",
            "added_tracks",
            "skipped_tracks",
            "failed_tracks",
            "error_message",
            "metadata",
            "created_at",
            "updated_at",
        )


class SyncJobDetailSerializer(SyncJobSerializer):
    items = SyncJobItemSerializer(many=True, read_only=True)

    class Meta(SyncJobSerializer.Meta):
        fields = SyncJobSerializer.Meta.fields + ("items",)


class MappingCandidateSerializer(serializers.ModelSerializer):
    source_track = ExternalTrackSerializer(read_only=True)
    target_track = ExternalTrackSerializer(read_only=True)

    class Meta:
        model = MappingCandidate
        fields = (
            "id",
            "source_track",
            "target_track",
            "score",
            "method",
            "status",
            "confirmed_by_user",
            "created_at",
        )


class MappingCandidateConfirmSerializer(serializers.Serializer):
    rule_id = serializers.UUIDField()

    def validate_rule_id(self, value):
        request = self.context["request"]
        try:
            rule = SyncRule.objects.get(id=value, user=request.user)
        except SyncRule.DoesNotExist as exc:
            raise serializers.ValidationError("Sync rule was not found.") from exc

        self.context["rule"] = rule
        return value


class PlaylistImportSerializer(serializers.Serializer):
    external_account_id = serializers.UUIDField()

    def validate_external_account_id(self, value):
        request = self.context["request"]
        try:
            account = ExternalAccount.objects.get(id=value, user=request.user)
        except ExternalAccount.DoesNotExist as exc:
            raise serializers.ValidationError("External account was not found.") from exc

        self.context["external_account"] = account
        return value
