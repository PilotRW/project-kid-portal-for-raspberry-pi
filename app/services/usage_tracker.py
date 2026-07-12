import json
import os
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field


class UsageStatus(BaseModel):
    date: str
    daily_limit_minutes: int
    used_seconds: int = Field(ge=0)
    remaining_seconds: int = Field(ge=0)
    limit_reached: bool


class PlaybackSession(BaseModel):
    session_id: str
    video_id: str
    started_at: datetime
    last_seen_at: datetime
    active: bool = True


class UsageState(BaseModel):
    date: str
    playback_seconds: int = Field(default=0, ge=0)
    sessions: dict[str, PlaybackSession] = Field(default_factory=dict)


class UsageTrackerService:
    def __init__(self, usage_path: Path | None = None, now_provider=None) -> None:
        default_path = Path(__file__).resolve().parents[2] / "config" / "usage.json"
        self.usage_path = usage_path or Path(os.environ.get("KID_PORTAL_USAGE", default_path))
        self.now_provider = now_provider or (lambda: datetime.now(UTC))

    def status(self, daily_limit_minutes: int) -> UsageStatus:
        state = self._load_today()
        limit_seconds = max(daily_limit_minutes, 1) * 60
        remaining = max(limit_seconds - state.playback_seconds, 0)
        return UsageStatus(
            date=state.date,
            daily_limit_minutes=daily_limit_minutes,
            used_seconds=state.playback_seconds,
            remaining_seconds=remaining,
            limit_reached=remaining <= 0,
        )

    def start_session(self, video_id: str, daily_limit_minutes: int) -> PlaybackSession:
        if self.status(daily_limit_minutes).limit_reached:
            raise RuntimeError("Daily viewing limit reached")
        state = self._load_today()
        now = self.now_provider()
        session = PlaybackSession(
            session_id=uuid4().hex,
            video_id=video_id,
            started_at=now,
            last_seen_at=now,
        )
        state.sessions[session.session_id] = session
        self._write(state)
        return session

    def heartbeat(self, session_id: str, player_state: str, daily_limit_minutes: int) -> UsageStatus:
        state = self._load_today()
        session = state.sessions.get(session_id)
        if not session or not session.active:
            return self.status(daily_limit_minutes)

        now = self.now_provider()
        if player_state == "playing":
            elapsed = max((now - session.last_seen_at).total_seconds(), 0)
            state.playback_seconds += min(int(elapsed), 30)

        session.last_seen_at = now
        state.sessions[session_id] = session
        status = self._status_from_state(state, daily_limit_minutes)
        if status.limit_reached:
            session.active = False
            state.sessions[session_id] = session
        self._write(state)
        return status

    def stop_session(self, session_id: str) -> None:
        state = self._load_today()
        session = state.sessions.get(session_id)
        if session:
            session.active = False
            session.last_seen_at = self.now_provider()
            state.sessions[session_id] = session
            self._write(state)

    def _status_from_state(self, state: UsageState, daily_limit_minutes: int) -> UsageStatus:
        limit_seconds = max(daily_limit_minutes, 1) * 60
        remaining = max(limit_seconds - state.playback_seconds, 0)
        return UsageStatus(
            date=state.date,
            daily_limit_minutes=daily_limit_minutes,
            used_seconds=state.playback_seconds,
            remaining_seconds=remaining,
            limit_reached=remaining <= 0,
        )

    def _load_today(self) -> UsageState:
        today = date.today().isoformat()
        if not self.usage_path.exists():
            return UsageState(date=today)
        raw = self.usage_path.read_text(encoding="utf-8").strip()
        if not raw:
            return UsageState(date=today)
        state = UsageState.model_validate(json.loads(raw))
        if state.date != today:
            return UsageState(date=today)
        return state

    def _write(self, state: UsageState) -> None:
        self.usage_path.parent.mkdir(parents=True, exist_ok=True)
        self.usage_path.write_text(json.dumps(state.model_dump(mode="json"), indent=2), encoding="utf-8")
