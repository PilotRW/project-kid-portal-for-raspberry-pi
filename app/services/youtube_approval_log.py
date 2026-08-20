import json
import os
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from app.services.filtering_engine import Decision, EvaluatedVideo


class YouTubeApprovalEntry(BaseModel):
    video_id: str
    title: str
    channel_id: str
    channel_title: str
    decision: Decision
    reasons: list[str] = Field(default_factory=list)
    approved_at: datetime


class YouTubeApprovalLogService:
    def __init__(self, log_path: Path | None = None, max_entries: int = 100) -> None:
        default_path = Path(__file__).resolve().parents[2] / "config" / "youtube-approval-log.json"
        self.log_path = log_path or Path(os.environ.get("KID_PORTAL_YOUTUBE_APPROVAL_LOG", default_path))
        self.max_entries = max_entries

    def list_entries(self) -> list[YouTubeApprovalEntry]:
        if not self.log_path.exists():
            return []
        raw = self.log_path.read_text(encoding="utf-8").strip()
        if not raw:
            return []
        data = json.loads(raw)
        return [YouTubeApprovalEntry.model_validate(item) for item in data]

    def add(self, evaluated: EvaluatedVideo) -> YouTubeApprovalEntry:
        video = evaluated.video
        entry = YouTubeApprovalEntry(
            video_id=video.video_id,
            title=video.title,
            channel_id=video.channel_id,
            channel_title=video.channel_title,
            decision=evaluated.decision,
            reasons=evaluated.reasons,
            approved_at=datetime.now(UTC),
        )
        self._write([entry, *self.list_entries()][: self.max_entries])
        return entry

    def clear(self) -> None:
        self._write([])

    def _write(self, entries: list[YouTubeApprovalEntry]) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [entry.model_dump(mode="json") for entry in entries]
        self.log_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
