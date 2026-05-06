from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import MappingCandidate, Playlist, PlaylistTrack, SyncJob, SyncRule
from .serializers import (
    MappingCandidateSerializer,
    MappingCandidateConfirmSerializer,
    PlaylistImportSerializer,
    PlaylistSerializer,
    PlaylistTrackSerializer,
    SyncJobDetailSerializer,
    SyncJobSerializer,
    SyncRuleSerializer,
)
from .services.candidate_resolution import MappingCandidateResolutionError, MappingCandidateResolutionService
from .services.executor import SyncExecutor
from .services.playlist_import import PlaylistImportService


class PlaylistListView(APIView):
    def get(self, request):
        queryset = Playlist.objects.filter(user=request.user).select_related("provider", "external_account")
        external_account_id = request.query_params.get("external_account")
        if external_account_id:
            queryset = queryset.filter(external_account_id=external_account_id)

        return Response(PlaylistSerializer(queryset.order_by("provider__code", "name"), many=True).data)


class PlaylistImportView(APIView):
    def post(self, request):
        serializer = PlaylistImportSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        service = PlaylistImportService()
        playlists = service.import_account_playlists(request.user, serializer.context["external_account"])

        return Response(
            {
                "imported_count": len(playlists),
                "playlists": PlaylistSerializer(playlists, many=True).data,
            },
            status=status.HTTP_200_OK,
        )


class PlaylistTrackListView(APIView):
    def get(self, request, playlist_id):
        playlist = get_object_or_404(Playlist, id=playlist_id, user=request.user)
        queryset = (
            PlaylistTrack.objects.filter(playlist=playlist)
            .select_related("external_track", "external_track__provider")
            .order_by("position")
        )
        return Response(PlaylistTrackSerializer(queryset, many=True).data)


class PlaylistTrackRefreshView(APIView):
    def post(self, request, playlist_id):
        playlist = get_object_or_404(Playlist, id=playlist_id, user=request.user)
        service = PlaylistImportService()
        tracks = service.import_playlist_tracks(playlist)

        queryset = (
            PlaylistTrack.objects.filter(playlist=playlist)
            .select_related("external_track", "external_track__provider")
            .order_by("position")
        )
        return Response(
            {
                "imported_count": len(tracks),
                "tracks": PlaylistTrackSerializer(queryset, many=True).data,
            }
        )


class SyncRuleListCreateView(APIView):
    def get(self, request):
        queryset = (
            SyncRule.objects.filter(user=request.user)
            .select_related("source_account__provider", "target_account__provider", "source_playlist", "target_playlist")
            .order_by("-created_at")
        )
        return Response(SyncRuleSerializer(queryset, many=True, context={"request": request}).data)

    def post(self, request):
        serializer = SyncRuleSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        rule = serializer.save()
        return Response(SyncRuleSerializer(rule, context={"request": request}).data, status=status.HTTP_201_CREATED)


class SyncRuleDetailView(APIView):
    def get_object(self, request, rule_id):
        return get_object_or_404(SyncRule, id=rule_id, user=request.user)

    def get(self, request, rule_id):
        rule = self.get_object(request, rule_id)
        return Response(SyncRuleSerializer(rule, context={"request": request}).data)

    def patch(self, request, rule_id):
        rule = self.get_object(request, rule_id)
        serializer = SyncRuleSerializer(rule, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        rule = serializer.save()
        return Response(SyncRuleSerializer(rule, context={"request": request}).data)

    def delete(self, request, rule_id):
        rule = self.get_object(request, rule_id)
        rule.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SyncRuleRunView(APIView):
    def post(self, request, rule_id):
        rule = get_object_or_404(SyncRule, id=rule_id, user=request.user, is_active=True)
        job = SyncExecutor().run_rule(rule)
        serializer_class = SyncJobDetailSerializer if job.items.exists() else SyncJobSerializer
        return Response(serializer_class(job).data, status=status.HTTP_201_CREATED)


class SyncJobListView(APIView):
    def get(self, request):
        queryset = (
            SyncJob.objects.filter(rule__user=request.user)
            .select_related("rule")
            .order_by("-created_at")
        )
        return Response(SyncJobSerializer(queryset, many=True).data)


class SyncJobDetailView(APIView):
    def get(self, request, job_id):
        job = get_object_or_404(SyncJob, id=job_id, rule__user=request.user)
        return Response(SyncJobDetailSerializer(job).data)


class MappingCandidateListView(APIView):
    def get(self, request):
        queryset = (
            MappingCandidate.objects.filter(user=request.user)
            .select_related("source_track__provider", "target_track__provider")
            .order_by("-created_at")
        )
        return Response(MappingCandidateSerializer(queryset, many=True).data)


class MappingCandidateConfirmView(APIView):
    def post(self, request, candidate_id):
        candidate = get_object_or_404(MappingCandidate, id=candidate_id, user=request.user)
        serializer = MappingCandidateConfirmSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        try:
            job = MappingCandidateResolutionService().confirm(
                request.user,
                candidate,
                serializer.context["rule"],
            )
        except MappingCandidateResolutionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "candidate": MappingCandidateSerializer(candidate).data,
                "job": SyncJobDetailSerializer(job).data,
            },
            status=status.HTTP_200_OK,
        )


class MappingCandidateRejectView(APIView):
    def post(self, request, candidate_id):
        candidate = get_object_or_404(MappingCandidate, id=candidate_id, user=request.user)

        try:
            candidate = MappingCandidateResolutionService().reject(request.user, candidate)
        except MappingCandidateResolutionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(MappingCandidateSerializer(candidate).data, status=status.HTTP_200_OK)
