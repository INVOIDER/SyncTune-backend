import re
import unicodedata


SPACE_RE = re.compile(r"\s+")
PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)


def normalize_text(value):
    if not value:
        return ""

    normalized = unicodedata.normalize("NFKD", str(value)).lower()
    normalized = PUNCT_RE.sub(" ", normalized)
    normalized = SPACE_RE.sub(" ", normalized)
    return normalized.strip()


def normalize_artists(artists):
    if isinstance(artists, str):
        value = artists
    else:
        value = " ".join(str(artist) for artist in artists or [] if artist)
    return normalize_text(value)


def build_track_query(track_data):
    title = track_data.get("title") or ""
    artists = track_data.get("artists") or track_data.get("artist") or ""
    if isinstance(artists, list):
        artists = " ".join(artists[:2])
    return " ".join(part for part in [title, artists] if part).strip()
