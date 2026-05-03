from django.urls import path

from integrations.views.yandex_music import YandexMusicConnectInfoView, YandexMusicTokenConnectView

urlpatterns = [
    path("connect/", YandexMusicConnectInfoView.as_view()),
    path("complete/", YandexMusicTokenConnectView.as_view()),
]
