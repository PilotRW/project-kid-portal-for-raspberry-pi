from datetime import UTC, datetime, timedelta

from app.services.filter_insights import FilterInsightsService


def test_filter_insights_dedupes_by_channel_and_title(tmp_path):
    service = FilterInsightsService(path=tmp_path / "insights.json", max_entries=150)

    service.record_gap("Channel A", "Odd Meme")
    service.record_gap(" channel a ", " odd   meme ")
    service.record_approval("Channel B", "Borderline Clip")

    gaps = service.top("gap")
    approvals = service.top("approval")
    assert len(gaps) == 1
    assert gaps[0].count == 2
    assert gaps[0].channel == "Channel A"
    assert gaps[0].title == "Odd Meme"
    assert [entry.title for entry in approvals] == ["Borderline Clip"]


def test_filter_insights_caps_oldest_entries(tmp_path):
    service = FilterInsightsService(path=tmp_path / "insights.json", max_entries=2)
    old = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    current = datetime.now(UTC).isoformat()
    service._write(
        {
            "gap::a::old": {"kind": "gap", "channel": "A", "title": "Old", "count": 1, "last_seen": old},
            "gap::b::current": {"kind": "gap", "channel": "B", "title": "Current", "count": 1, "last_seen": current},
        }
    )

    service.record_gap("C", "New")

    titles = {entry.title for entry in service.top(limit=10)}
    assert titles == {"Current", "New"}
