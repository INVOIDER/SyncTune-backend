from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from integrations.models import ExternalAccount, MusicProvider
from integrations.security import encrypt_token
from integrations.services.yandex_music import YandexMusicAPIError, YandexMusicService

PROVIDER_CODE = "yandex_music"


class YandexMusicConnectInfoView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not MusicProvider.objects.filter(code=PROVIDER_CODE, is_active=True).exists():
            return Response(
                {"detail": "Yandex Music provider is not configured or is inactive."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        service = YandexMusicService()

        return Response(
            {
                "provider": PROVIDER_CODE,
                "connection_method": "manual_token",
                "official_oauth_supported": False,
                "api_library": "yandex-music",
                "token_url": service.get_authorization_url(),
                "complete_endpoint": "/api/providers/yandex-music/complete/",
                "instructions": [
                    "Yandex Music has no Spotify-like public OAuth for custom apps.",
                    "Open token_url in a browser and sign in to Yandex.",
                    "Copy access_token from the redirected URL fragment.",
                    "The backend will validate this token with yandex-music Client(token).init().",
                    "Send the token to complete_endpoint as JSON: {\"access_token\": \"...\"}.",
                ],
            }
        )


class YandexMusicTokenConnectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = request.data.get("access_token") or request.data.get("token")
        if not token or not token.strip():
            return Response(
                {"detail": "access_token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        service = YandexMusicService()

        try:
            provider = MusicProvider.objects.get(code=PROVIDER_CODE, is_active=True)
        except MusicProvider.DoesNotExist:
            return Response(
                {"detail": "Yandex Music provider is not configured or is inactive."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            profile = service.get_user_profile(token)
        except YandexMusicAPIError as exc:
            response_status = status.HTTP_502_BAD_GATEWAY if exc.status_code >= 500 else status.HTTP_400_BAD_REQUEST
            return Response(
                {
                    "detail": "Yandex Music API request failed.",
                    "yandex_music_status": exc.status_code,
                    "yandex_music_error": exc.message,
                },
                status=response_status,
            )

        normalized_token = service.normalize_token(token)
        account, _ = ExternalAccount.objects.update_or_create(
            user=request.user,
            provider=provider,
            external_user_id=profile["external_user_id"],
            defaults={
                "display_name": profile["display_name"],
                "access_token_encrypted": encrypt_token(normalized_token),
                "refresh_token_encrypted": None,
                "token_expires_at": None,
                "scopes": [],
                "status": "active",
                "metadata": profile["metadata"],
                "last_reauthorized_at": timezone.now(),
            },
        )

        return Response(
            {
                "status": "connected",
                "provider": PROVIDER_CODE,
                "external_account_id": str(account.id),
                "external_user_id": account.external_user_id,
                "display_name": account.display_name,
            }
        )
