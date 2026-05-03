from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from integrations.models import ExternalAccount, MusicProvider
from integrations.security import encrypt_token
from integrations.services.spotify import SpotifyAPIError, SpotifyService

User = get_user_model()
PROVIDER_CODE = "spotify"


class SpotifyAuthStartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not MusicProvider.objects.filter(code=PROVIDER_CODE, is_active=True).exists():
            return Response(
                {"detail": "Spotify provider is not configured or is inactive."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        service = SpotifyService()
        url, state = service.get_authorization_url()

        request.session["oauth_state"] = state
        request.session["oauth_user_id"] = str(request.user.pk)
        request.session["oauth_provider"] = PROVIDER_CODE

        return Response({"auth_url": url})


class SpotifyCallbackView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        error = request.GET.get("error")
        if error:
            return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)

        code = request.GET.get("code")
        state = request.GET.get("state")
        expected_state = request.session.pop("oauth_state", None)
        user_id = request.session.pop("oauth_user_id", None)
        provider_code = request.session.pop("oauth_provider", None)

        if not code:
            return Response({"detail": "Authorization code is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not expected_state or state != expected_state or provider_code != PROVIDER_CODE:
            return Response({"detail": "Invalid OAuth state."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({"detail": "OAuth session user was not found."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            provider = MusicProvider.objects.get(code=PROVIDER_CODE, is_active=True)
        except MusicProvider.DoesNotExist:
            return Response(
                {"detail": "Spotify provider is not configured or is inactive."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        service = SpotifyService()
        try:
            token = service.fetch_token(code)
            profile = service.get_user_profile(token)
        except SpotifyAPIError as exc:
            response_status = status.HTTP_502_BAD_GATEWAY if exc.status_code >= 500 else status.HTTP_400_BAD_REQUEST
            return Response(
                {
                    "detail": "Spotify API request failed.",
                    "spotify_status": exc.status_code,
                    "spotify_error": exc.message,
                },
                status=response_status,
            )

        account, _ = ExternalAccount.objects.update_or_create(
            user=user,
            provider=provider,
            external_user_id=profile["id"],
            defaults={
                "display_name": profile.get("display_name"),
                "access_token_encrypted": encrypt_token(token["access_token"]),
                "refresh_token_encrypted": encrypt_token(token.get("refresh_token")),
                "token_expires_at": timezone.now()
                + timezone.timedelta(seconds=token["expires_in"]),
                "scopes": token.get("scope", "").split(),
                "status": "active",
                "last_reauthorized_at": timezone.now(),
            },
        )

        return Response({
            "status": "connected",
            "provider": PROVIDER_CODE,
            "external_account_id": str(account.id),
        })
