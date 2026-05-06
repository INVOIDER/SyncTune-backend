from difflib import SequenceMatcher

from .normalization import build_track_query, normalize_artists, normalize_text


class TrackMatcher:
    MIN_ACCEPT_SCORE = 0.82
    MIN_CONFLICT_SCORE = 0.62

    def find_best_match(self, source_track_data, target_service, target_token):
        query = build_track_query(source_track_data)
        if not query:
            return None

        candidates = target_service.search_tracks(target_token, query)
        scored = [
            self.score_candidate(source_track_data, candidate)
            for candidate in candidates
            if candidate.get("external_track_id")
        ]
        scored = [candidate for candidate in scored if candidate["score"] >= self.MIN_CONFLICT_SCORE]

        if not scored:
            return None

        return max(scored, key=lambda candidate: candidate["score"])

    def score_candidate(self, source_track_data, target_track_data):
        source_isrc = (source_track_data.get("isrc") or "").strip().lower()
        target_isrc = (target_track_data.get("isrc") or "").strip().lower()
        if source_isrc and target_isrc and source_isrc == target_isrc:
            return {
                "track": target_track_data,
                "score": 1.0,
                "method": "isrc",
            }

        source_title = normalize_text(source_track_data.get("title"))
        target_title = normalize_text(target_track_data.get("title"))
        source_artists = normalize_artists(source_track_data.get("artists") or source_track_data.get("artist"))
        target_artists = normalize_artists(target_track_data.get("artists") or target_track_data.get("artist"))

        title_score = SequenceMatcher(None, source_title, target_title).ratio()
        artist_score = SequenceMatcher(None, source_artists, target_artists).ratio()
        duration_score = self._duration_score(
            source_track_data.get("duration_ms"),
            target_track_data.get("duration_ms"),
        )

        score = (title_score * 0.55) + (artist_score * 0.35) + (duration_score * 0.10)

        return {
            "track": target_track_data,
            "score": round(score, 4),
            "method": "metadata",
        }

    def same_track(self, source_track_data, target_track_data):
        return self.score_candidate(source_track_data, target_track_data)["score"] >= self.MIN_ACCEPT_SCORE

    def _duration_score(self, source_duration, target_duration):
        if not source_duration or not target_duration:
            return 0.5

        difference = abs(int(source_duration) - int(target_duration))
        if difference <= 3000:
            return 1.0
        if difference <= 10000:
            return 0.75
        if difference <= 30000:
            return 0.35
        return 0.0
