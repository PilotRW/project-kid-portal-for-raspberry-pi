from datetime import UTC, datetime, timedelta

from app.services.filtering_engine import VideoCandidate
from app.services.youtube_search_cache import YouTubeSearchCacheService


def candidate(video_id: str = "abc") -> VideoCandidate:
    return VideoCandidate(
        video_id=video_id,
        title="A cached result",
        description="",
        channel_id="channel-a",
        channel_title="Channel A",
        category="27",
        duration_seconds=300,
        thumbnail_url="https://i.ytimg.com/example.jpg",
    )


def test_cache_returns_normalized_query_hits(tmp_path):
    service = YouTubeSearchCacheService(cache_path=tmp_path / "cache.json", ttl_seconds=7 * 24 * 60 * 60)

    service.set("  lego   train ", 20, "strict", [candidate()])

    cached = service.get("lego train", 20, "strict")
    assert cached is not None
    assert [item.video_id for item in cached] == ["abc"]


def test_cache_misses_different_search_settings(tmp_path):
    service = YouTubeSearchCacheService(cache_path=tmp_path / "cache.json")

    service.set("lego", 20, "strict", [candidate()])

    assert service.get("lego", 12, "strict") is None
    assert service.get("lego", 20, "moderate") is None


def test_cache_prunes_expired_entries(tmp_path):
    service = YouTubeSearchCacheService(cache_path=tmp_path / "cache.json", ttl_seconds=1)
    expired = {
        "query": "lego",
        "limit": 20,
        "safe_search": "strict",
        "cached_at": (datetime.now(UTC) - timedelta(days=8)).isoformat(),
        "expires_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
        "results": [candidate().model_dump(mode="json")],
    }
    cache_key = service._cache_key("lego", 20, "strict")
    service._write({cache_key: expired})

    assert service.get("lego", 20, "strict") is None
    assert service._load() == {}
