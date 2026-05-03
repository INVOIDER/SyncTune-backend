from django.urls import include, path

urlpatterns = [
    path("spotify/", include("integrations.urls.spotify")),
    path("yandex-music/", include("integrations.urls.yandex_music")),
]
