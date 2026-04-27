from django.urls import path
from ..views import SpotifyAuthStartView, SpotifyCallbackView

urlpatterns = [
    path("connect/", SpotifyAuthStartView.as_view()),
    path("callback/", SpotifyCallbackView.as_view()),
]