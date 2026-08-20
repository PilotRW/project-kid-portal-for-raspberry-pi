import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

InsightKind = Literal["gap", "approval"]


class FilterInsightEntry(BaseModel):
    kind: InsightKind
    channel: str
    title: str
    count: int = Field(ge=0)
    last_seen: datetime


class FilterInsightsService:
    def __init__(self, path: Path | None = None, max_entries: int = 150) -> None:
        default_path = Path(__file__).resolve().parents[2] / "config" / "filter-insights.json"
        self.path = path or Path(os.environ.get("KID_PORTAL_FILTER_INSIGHTS", default_path))
        self.max_entries = max_entries

    def record_gap(self, channel_title: str, title: str) -> None:
        self._record("gap", channel_title, title)

    def record_approval(self, channel_title: str, title: str) -> None:
        self._record("approval", channel_title, title)

    def top(self, kind: InsightKind | None = None, limit: int = 15) -> list[FilterInsightEntry]:
        entries = self._load().values()
        parsed = []
        for value in entries:
            try:
                entry = FilterInsightEntry.model_validate(value)
            except ValueError:
                continue
            if kind is None or entry.kind == kind:
                parsed.append(entry)
        return sorted(parsed, key=lambda entry: (-entry.count, entry.last_seen), reverse=False)[:limit]

    def _record(self, kind: InsightKind, channel_title: str, title: str) -> None:
        normalized_channel = " ".join(channel_title.strip().split())
        normalized_title = " ".join(title.strip().split())
        if not normalized_title:
            return
        key = f"{kind}::{normalized_channel.casefold()}::{normalized_title.casefold()}"
        data = self._load()
        now = datetime.now(UTC)
        entry = data.get(
            key,
            {
                "kind": kind,
                "channel": normalized_channel,
                "title": normalized_title,
                "count": 0,
                "last_seen": now.isoformat(),
            },
        )
        entry["count"] = int(entry.get("count", 0)) + 1
        entry["last_seen"] = now.isoformat()
        data[key] = entry
        while len(data) > self.max_entries:
            oldest_key = min(data, key=lambda item: data[item].get("last_seen", ""))
            data.pop(oldest_key)
        self._write(data)

    def _load(self) -> dict[str, object]:
        if not self.path.exists():
            return {}
        raw = self.path.read_text(encoding="utf-8").strip()
        if not raw:
            return {}
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}

    def _write(self, data: dict[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
