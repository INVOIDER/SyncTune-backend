from django.urls import path
from integrations.views.spotify import SpotifyAuthStartView, SpotifyCallbackView

urlpatterns = [
    path("connect/", SpotifyAuthStartView.as_view()),
    path("callback/", SpotifyCallbackView.as_view()),
]
