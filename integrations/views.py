# apps/integrations/views.py
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from integrations.services.spotify import SpotifyService
from integrations.models import ExternalAccount, MusicProvider

class SpotifyAuthStartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        service = SpotifyService()
        url, state = service.get_authorization_url()

        request.session["oauth_state"] = state

        return Response({"auth_url": url})

class SpotifyCallbackView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        code = request.GET.get("code")

        service = SpotifyService()
        token = service.fetch_token(code)
        profile = service.get_user_profile(token)

        provider = MusicProvider.objects.get(code="spotify")

        account, _ = ExternalAccount.objects.update_or_create(
            user=request.user,
            provider=provider,
            external_user_id=profile["id"],
            defaults={
                "display_name": profile.get("display_name"),
                "access_token_encrypted": token["access_token"].encode(),
                "refresh_token_encrypted": token.get("refresh_token", "").encode(),
                "token_expires_at": timezone.now()
                + timezone.timedelta(seconds=token["expires_in"]),
                "scopes": token.get("scope", "").split(),
                "status": "active",
                "last_reauthorized_at": timezone.now(),
            },
        )

        return Response({
            "status": "connected",
            "provider": "spotify",
            "external_account_id": str(account.id),
        })