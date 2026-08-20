from enum import StrEnum

from pydantic import BaseModel

from app.services.config_service import FilteringConfig

YOUTUBE_CATEGORY_NAMES = {
    "1": "Film & Animation",
    "2": "Autos & Vehicles",
    "10": "Music",
    "15": "Pets & Animals",
    "17": "Sports",
    "19": "Travel & Events",
    "20": "Gaming",
    "22": "People & Blogs",
    "23": "Comedy",
    "24": "Entertainment",
    "25": "News & Politics",
    "26": "Howto & Style",
    "27": "Education",
    "28": "Science & Technology",
}


class Decision(StrEnum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    REQUIRE_PARENT_APPROVAL = "REQUIRE_PARENT_APPROVAL"


class VideoCandidate(BaseModel):
    video_id: str
    title: str
    description: str = ""
    channel_id: str
    channel_title: str
    category: str | None = None
    duration_seconds: int | None = None
    thumbnail_url: str | None = None


class EvaluatedVideo(BaseModel):
    video: VideoCandidate
    decision: Decision
    reasons: list[str]


class FilteringEngine:
    def __init__(self, config: FilteringConfig) -> None:
        self.config = config

    def evaluate_video(self, video: VideoCandidate) -> EvaluatedVideo:
        reasons: list[str] = []
        text = f"{video.title} {video.description} {video.channel_title} {video.category or ''}".lower()
        channel_tokens = {video.channel_id.lower(), video.channel_title.lower()}

        if self._matches_any(channel_tokens, self.config.allowed_channels):
            reasons.append("channel whitelist")
            return EvaluatedVideo(video=video, decision=Decision.ALLOW, reasons=reasons)

        if self._matches_any(channel_tokens, self.config.blocked_channels):
            reasons.append("channel blacklist")
            return EvaluatedVideo(video=video, decision=Decision.BLOCK, reasons=reasons)

        blocked_hits = self._keyword_hits(text, self.config.blocked_keywords)
        if blocked_hits:
            reasons.extend(f"blocked keyword: {hit}" for hit in blocked_hits)
            return EvaluatedVideo(video=video, decision=Decision.BLOCK, reasons=reasons)

        if self._category_matches(video.category, self.config.blocked_categories):
            category = self._category_label(video.category)
            reasons.append(f"blocked category: {category}")
            return EvaluatedVideo(video=video, decision=Decision.BLOCK, reasons=reasons)

        if video.duration_seconds is not None and self.config.short_video_max_seconds:
            if video.duration_seconds < self.config.short_video_max_seconds:
                reasons.append(f"short video under {self.config.short_video_max_seconds} seconds")
                return EvaluatedVideo(video=video, decision=Decision(self.config.short_video_decision), reasons=reasons)

        approval_hits = self._keyword_hits(text, self.config.approval_keywords)
        if approval_hits:
            reasons.extend(f"approval keyword: {hit}" for hit in approval_hits)
            return EvaluatedVideo(video=video, decision=Decision.REQUIRE_PARENT_APPROVAL, reasons=reasons)

        allowed_hits = self._keyword_hits(text, self.config.allowed_keywords)
        if allowed_hits:
            reasons.extend(f"allowed keyword: {hit}" for hit in allowed_hits)
            return EvaluatedVideo(video=video, decision=Decision.ALLOW, reasons=reasons)

        if video.duration_seconds and self.config.max_duration_seconds:
            if video.duration_seconds > self.config.max_duration_seconds:
                reasons.append("duration exceeds configured limit")
                return EvaluatedVideo(video=video, decision=Decision.REQUIRE_PARENT_APPROVAL, reasons=reasons)

        reasons.append(f"default decision: {self.config.default_decision.lower()}")
        return EvaluatedVideo(video=video, decision=Decision(self.config.default_decision), reasons=reasons)

    @staticmethod
    def _matches_any(values: set[str], configured: list[str]) -> bool:
        wanted = {item.lower() for item in configured}
        return bool(values & wanted)

    @staticmethod
    def _keyword_hits(text: str, keywords: list[str]) -> list[str]:
        return [keyword for keyword in keywords if keyword.lower() in text]

    @staticmethod
    def _category_matches(category: str | None, configured: list[str]) -> bool:
        if not category:
            return False
        normalized = {item.strip().lower() for item in configured}
        category_id = category.strip().lower()
        category_name = FilteringEngine._category_label(category).lower()
        return category_id in normalized or category_name in normalized

    @staticmethod
    def _category_label(category: str | None) -> str:
        if not category:
            return "unknown"
        return YOUTUBE_CATEGORY_NAMES.get(category, category)
