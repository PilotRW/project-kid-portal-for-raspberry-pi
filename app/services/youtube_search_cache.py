import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.services.filtering_engine import VideoCandidate


class YouTubeSearchCacheEntry(BaseModel):
    query: str
    limit: int
    safe_search: str
    cached_at: datetime
    expires_at: datetime
    results: list[VideoCandidate]


class YouTubeSearchCacheService:
    def __init__(
        self,
        cache_path: Path | None = None,
        ttl_seconds: int | None = None,
    ) -> None:
        default_path = Path(__file__).resolve().parents[2] / "config" / "youtube-search-cache.json"
        self.cache_path = cache_path or Path(os.environ.get("KID_PORTAL_YOUTUBE_SEARCH_CACHE", default_path))
        self.ttl_seconds = ttl_seconds or int(
            os.environ.get("KID_PORTAL_YOUTUBE_SEARCH_CACHE_TTL_SECONDS", str(7 * 24 * 60 * 60))
        )

    def get(self, query: str, limit: int, safe_search: str) -> list[VideoCandidate] | None:
        entries = self._load()
        key = self._cache_key(query, limit, safe_search)
        entry_data = entries.get(key)
        if not entry_data:
            return None
        try:
            entry = YouTubeSearchCacheEntry.model_validate(entry_data)
        except ValueError:
            entries.pop(key, None)
            self._write(entries)
            return None
        if entry.expires_at <= datetime.now(UTC):
            entries.pop(key, None)
            self._write(entries)
            return None
        return entry.results

    def set(self, query: str, limit: int, safe_search: str, results: list[VideoCandidate]) -> None:
        entries = self._pruned_entries()
        now = datetime.now(UTC)
        entry = YouTubeSearchCacheEntry(
            query=self._normalize_query(query),
            limit=limit,
            safe_search=safe_search,
            cached_at=now,
            expires_at=now + timedelta(seconds=self.ttl_seconds),
            results=results,
        )
        entries[self._cache_key(query, limit, safe_search)] = entry.model_dump(mode="json")
        self._write(entries)

    def clear(self) -> None:
        self._write({})

    def _pruned_entries(self) -> dict[str, Any]:
        now = datetime.now(UTC)
        pruned: dict[str, Any] = {}
        for key, value in self._load().items():
            try:
                entry = YouTubeSearchCacheEntry.model_validate(value)
            except ValueError:
                continue
            if entry.expires_at > now:
                pruned[key] = entry.model_dump(mode="json")
        return pruned

    def _load(self) -> dict[str, Any]:
        if not self.cache_path.exists():
            return {}
        raw = self.cache_path.read_text(encoding="utf-8").strip()
        if not raw:
            return {}
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}

    def _write(self, entries: dict[str, Any]) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(entries, indent=2, sort_keys=True), encoding="utf-8")

    @classmethod
    def _cache_key(cls, query: str, limit: int, safe_search: str) -> str:
        payload = {
            "query": cls._normalize_query(query).casefold(),
            "limit": limit,
            "safe_search": safe_search,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    @staticmethod
    def _normalize_query(query: str) -> str:
        return " ".join(query.strip().split())
