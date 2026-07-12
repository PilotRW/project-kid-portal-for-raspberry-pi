import json
import os
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field


class SearchHistoryEntry(BaseModel):
    query: str
    searched_at: datetime
    result_count: int = Field(ge=0)
    mode: str


class SearchHistoryService:
    def __init__(self, history_path: Path | None = None, max_entries: int = 20) -> None:
        default_path = Path(__file__).resolve().parents[2] / "config" / "search-history.json"
        self.history_path = history_path or Path(os.environ.get("KID_PORTAL_SEARCH_HISTORY", default_path))
        self.max_entries = max_entries

    def list_entries(self) -> list[SearchHistoryEntry]:
        if not self.history_path.exists():
            return []
        raw = self.history_path.read_text(encoding="utf-8").strip()
        if not raw:
            return []
        data = json.loads(raw)
        return [SearchHistoryEntry.model_validate(item) for item in data]

    def add(self, query: str, result_count: int, mode: str) -> SearchHistoryEntry:
        normalized_query = " ".join(query.strip().split())
        entry = SearchHistoryEntry(
            query=normalized_query,
            searched_at=datetime.now(UTC),
            result_count=result_count,
            mode=mode,
        )
        existing = [item for item in self.list_entries() if item.query.casefold() != normalized_query.casefold()]
        self._write([entry, *existing][: self.max_entries])
        return entry

    def clear(self) -> None:
        self._write([])

    def _write(self, entries: list[SearchHistoryEntry]) -> None:
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [entry.model_dump(mode="json") for entry in entries]
        self.history_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
