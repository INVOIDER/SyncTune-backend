from .spotify import SpotifyService
from .yandex_music import YandexMusicService


SERVICE_REGISTRY = {
    SpotifyService.provider_code: SpotifyService,
    YandexMusicService.provider_code: YandexMusicService,
}


def get_music_service(provider_code):
    service_class = SERVICE_REGISTRY.get(provider_code)
    if not service_class:
        raise ValueError(f"Unsupported music provider: {provider_code}")
    return service_class()
