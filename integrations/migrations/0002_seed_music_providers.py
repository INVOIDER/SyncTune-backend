from django.db import migrations


PROVIDERS = [
    {
        "code": "spotify",
        "name": "Spotify",
        "api_base_url": "https://api.spotify.com/v1",
        "supports_oauth": True,
        "is_active": True,
        "metadata": {
            "connection_method": "oauth",
            "official_oauth_supported": True,
        },
    },
    {
        "code": "yandex_music",
        "name": "Yandex Music",
        "api_base_url": "https://api.music.yandex.net",
        "supports_oauth": False,
        "is_active": True,
        "metadata": {
            "connection_method": "manual_token",
            "official_oauth_supported": False,
            "api_library": "yandex-music",
        },
    },
]


def seed_music_providers(apps, schema_editor):
    MusicProvider = apps.get_model("integrations", "MusicProvider")

    for provider in PROVIDERS:
        MusicProvider.objects.get_or_create(
            code=provider["code"],
            defaults={
                "name": provider["name"],
                "api_base_url": provider["api_base_url"],
                "supports_oauth": provider["supports_oauth"],
                "is_active": provider["is_active"],
                "metadata": provider["metadata"],
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_music_providers, migrations.RunPython.noop),
    ]
