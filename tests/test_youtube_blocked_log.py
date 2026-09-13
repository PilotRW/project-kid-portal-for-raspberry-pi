from app.services.filtering_engine import Decision, EvaluatedVideo, VideoCandidate
from app.services.youtube_blocked_log import YouTubeBlockedLogService


def candidate(video_id: str = "abc123") -> VideoCandidate:
    return VideoCandidate(
        video_id=video_id,
        title="Blocked cartoon",
        description="",
        channel_id="channel-a",
        channel_title="Channel A",
        category="22",
        duration_seconds=120,
    )


def test_blocked_log_records_blocked_entries_only(tmp_path):
    service = YouTubeBlockedLogService(log_path=tmp_path / "blocked.json", max_entries=2)

    ignored = service.add(EvaluatedVideo(video=candidate("allowed"), decision=Decision.ALLOW, reasons=["allowed keyword"]))
    service.add(EvaluatedVideo(video=candidate("one"), decision=Decision.BLOCK, reasons=["blocked keyword: prank"]))
    service.add(EvaluatedVideo(video=candidate("two"), decision=Decision.BLOCK, reasons=["blocked category: Gaming"]))
    service.add(EvaluatedVideo(video=candidate("three"), decision=Decision.BLOCK, reasons=["blocked keyword: pee"]))

    entries = service.list_entries()
    assert ignored is None
    assert [entry.video_id for entry in entries] == ["three", "two"]
    assert entries[0].reasons == ["blocked keyword: pee"]
