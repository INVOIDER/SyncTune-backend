from django.urls import include, path

urlpatterns = [
    path("spotify/", include("integrations.urls.spotify")),
]
