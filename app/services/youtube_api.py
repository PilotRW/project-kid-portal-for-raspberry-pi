import os
import re
from pathlib import Path

import httpx

from app.services.filtering_engine import VideoCandidate


ISO_DURATION_RE = re.compile(
    r"^PT(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?$"
)


class YouTubeApiService:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key
        self.default_key_file = Path(__file__).resolve().parents[2] / "config" / "youtube-api-key.txt"

    @property
    def is_configured(self) -> bool:
        return bool(self._resolve_api_key())

    def status(self) -> dict[str, str | bool]:
        key = self._resolve_api_key()
        return {
            "configured": bool(key),
            "mode": "live" if key else "demo",
            "source": self._key_source() if key else "none",
        }

    async def search(self, query: str, limit: int = 12, safe_search: str = "strict") -> list[VideoCandidate]:
        api_key = self._resolve_api_key()
        if not api_key:
            return self._demo_results(query)

        async with httpx.AsyncClient(timeout=10) as client:
            search_response = await client.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={
                    "part": "snippet",
                    "q": query,
                    "type": "video",
                    "videoEmbeddable": "true",
                    "maxResults": limit,
                    "safeSearch": safe_search,
                    "key": api_key,
                },
            )
            self._raise_for_api_error(search_response, "search")
            search_items = search_response.json().get("items", [])
            video_ids = [item["id"]["videoId"] for item in search_items if item.get("id", {}).get("videoId")]
            if not video_ids:
                return []

            details_response = await client.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={
                    "part": "snippet,contentDetails,status",
                    "id": ",".join(video_ids),
                    "key": api_key,
                },
            )
            self._raise_for_api_error(details_response, "video details")
            details_by_id = {item["id"]: item for item in details_response.json().get("items", [])}

        return [
            self._candidate_from_item(item, details_by_id)
            for item in search_items
            if details_by_id.get(item.get("id", {}).get("videoId"), {}).get("status", {}).get("embeddable", True)
        ]

    def _candidate_from_item(self, item: dict, details_by_id: dict[str, dict]) -> VideoCandidate:
        video_id = item["id"]["videoId"]
        snippet = item["snippet"]
        details = details_by_id.get(video_id, {})
        content_details = details.get("contentDetails", {})
        detail_snippet = details.get("snippet", {})
        return VideoCandidate(
            video_id=video_id,
            title=snippet.get("title", ""),
            description=snippet.get("description", ""),
            channel_id=snippet.get("channelId", ""),
            channel_title=snippet.get("channelTitle", ""),
            category=detail_snippet.get("categoryId"),
            duration_seconds=parse_iso8601_duration(content_details.get("duration")),
            thumbnail_url=self._thumbnail_url(snippet.get("thumbnails", {})),
        )

    @staticmethod
    def _demo_results(query: str) -> list[VideoCandidate]:
        return [
            VideoCandidate(
                video_id="demo-science",
                title=f"Science basics for kids: {query}",
                description="A calm educational demo result shown until YOUTUBE_API_KEY is configured.",
                channel_id="demo-education",
                channel_title="Demo Learning Channel",
                category="Science",
                duration_seconds=600,
                thumbnail_url=None,
            ),
            VideoCandidate(
                video_id="demo-clickbait",
                title=f"Extreme prank challenge with {query}",
                description="Demo unsafe-looking result to prove filtering works.",
                channel_id="demo-pranks",
                channel_title="Demo Prank Channel",
                category="Entertainment",
                duration_seconds=500,
                thumbnail_url=None,
            ),
        ]

    def _resolve_api_key(self) -> str | None:
        if self.api_key:
            return self.api_key
        env_key = os.environ.get("YOUTUBE_API_KEY")
        if env_key:
            return env_key.strip()
        key_file = Path(os.environ.get("YOUTUBE_API_KEY_FILE", self.default_key_file))
        if key_file.exists():
            value = key_file.read_text(encoding="utf-8").strip()
            return value or None
        return None

    def _key_source(self) -> str:
        if self.api_key:
            return "constructor"
        if os.environ.get("YOUTUBE_API_KEY"):
            return "env:YOUTUBE_API_KEY"
        key_file = Path(os.environ.get("YOUTUBE_API_KEY_FILE", self.default_key_file))
        if key_file.exists() and key_file.read_text(encoding="utf-8").strip():
            return str(key_file)
        return "none"

    @staticmethod
    def _raise_for_api_error(response: httpx.Response, operation: str) -> None:
        if response.status_code < 400:
            return
        message = f"YouTube API {operation} failed with HTTP {response.status_code}."
        reason = None
        try:
            error = response.json().get("error", {})
            reason = error.get("message")
        except ValueError:
            reason = None
        if response.status_code == 429:
            message = "YouTube API quota is exhausted or rate-limited. Try again after the quota resets."
        elif response.status_code in {400, 403} and reason:
            message = f"YouTube API rejected the request: {reason}"
        raise YouTubeApiError(status_code=response.status_code, detail=message)

    @staticmethod
    def _thumbnail_url(thumbnails: dict) -> str | None:
        for size in ("medium", "high", "standard", "maxres", "default"):
            url = thumbnails.get(size, {}).get("url")
            if url:
                return url
        return None


def parse_iso8601_duration(value: str | None) -> int | None:
    if not value:
        return None
    match = ISO_DURATION_RE.match(value)
    if not match:
        return None
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    return hours * 3600 + minutes * 60 + seconds


class YouTubeApiError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)
