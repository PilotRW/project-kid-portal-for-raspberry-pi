from app.services.filtering_engine import Decision, EvaluatedVideo, VideoCandidate
from app.services.youtube_approval_log import YouTubeApprovalLogService


def candidate(video_id: str = "abc123") -> VideoCandidate:
    return VideoCandidate(
        video_id=video_id,
        title="Plain cartoon",
        description="",
        channel_id="channel-a",
        channel_title="Channel A",
        category="22",
        duration_seconds=120,
    )


def test_approval_log_records_latest_entries_first(tmp_path):
    service = YouTubeApprovalLogService(log_path=tmp_path / "approvals.json", max_entries=2)

    service.add(EvaluatedVideo(video=candidate("one"), decision=Decision.REQUIRE_PARENT_APPROVAL, reasons=["default decision"]))
    service.add(EvaluatedVideo(video=candidate("two"), decision=Decision.ALLOW, reasons=["channel whitelist"]))
    service.add(EvaluatedVideo(video=candidate("three"), decision=Decision.REQUIRE_PARENT_APPROVAL, reasons=["short video under 60 seconds"]))

    entries = service.list_entries()
    assert [entry.video_id for entry in entries] == ["three", "two"]
    assert entries[0].reasons == ["short video under 60 seconds"]
