from datetime import UTC, datetime, timedelta

from app.services.usage_tracker import UsageTrackerService


def test_usage_counts_only_playing_heartbeats(tmp_path):
    now = datetime(2026, 7, 12, 12, 0, tzinfo=UTC)

    def now_provider():
        return now

    service = UsageTrackerService(usage_path=tmp_path / "usage.json", now_provider=now_provider)
    session = service.start_session("video-1", daily_limit_minutes=1)

    now += timedelta(seconds=20)
    paused = service.heartbeat(session.session_id, "paused", daily_limit_minutes=1)
    assert paused.used_seconds == 0

    now += timedelta(seconds=20)
    playing = service.heartbeat(session.session_id, "playing", daily_limit_minutes=1)
    assert playing.used_seconds == 20
    assert playing.limit_reached is False


def test_usage_reaches_daily_limit(tmp_path):
    now = datetime(2026, 7, 12, 12, 0, tzinfo=UTC)

    def now_provider():
        return now

    service = UsageTrackerService(usage_path=tmp_path / "usage.json", now_provider=now_provider)
    session = service.start_session("video-1", daily_limit_minutes=1)

    for _ in range(3):
        now += timedelta(seconds=30)
        status = service.heartbeat(session.session_id, "playing", daily_limit_minutes=1)

    assert status.used_seconds == 60
    assert status.remaining_seconds == 0
    assert status.limit_reached is True
