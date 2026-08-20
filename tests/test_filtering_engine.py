from app.services.config_service import FilteringConfig
from app.services.filtering_engine import Decision, FilteringEngine, VideoCandidate


def candidate(**overrides):
    data = {
        "video_id": "v1",
        "title": "Calm science for kids",
        "description": "",
        "channel_id": "channel-1",
        "channel_title": "Learning",
        "category": "Science",
        "duration_seconds": 300,
    }
    data.update(overrides)
    return VideoCandidate(**data)


def test_channel_whitelist_allows_first():
    engine = FilteringEngine(FilteringConfig(allowed_channels=["Learning"], blocked_keywords=["science"]))
    result = engine.evaluate_video(candidate())
    assert result.decision == Decision.ALLOW
    assert "channel whitelist" in result.reasons


def test_channel_blacklist_blocks():
    engine = FilteringEngine(FilteringConfig(blocked_channels=["Learning"]))
    result = engine.evaluate_video(candidate())
    assert result.decision == Decision.BLOCK


def test_keyword_blacklist_blocks():
    engine = FilteringEngine(FilteringConfig(blocked_keywords=["prank"]))
    result = engine.evaluate_video(candidate(title="Prank challenge"))
    assert result.decision == Decision.BLOCK


def test_approval_keyword_requires_parent():
    engine = FilteringEngine(FilteringConfig(approval_keywords=["gaming"]))
    result = engine.evaluate_video(candidate(title="Gaming history"))
    assert result.decision == Decision.REQUIRE_PARENT_APPROVAL


def test_long_duration_requires_parent():
    engine = FilteringEngine(FilteringConfig(max_duration_seconds=100))
    result = engine.evaluate_video(candidate(duration_seconds=101))
    assert result.decision == Decision.REQUIRE_PARENT_APPROVAL


def test_blocked_category_blocks_gaming():
    engine = FilteringEngine(FilteringConfig(blocked_categories=["20"]))
    result = engine.evaluate_video(candidate(category="20", title="Minecraft village"))
    assert result.decision == Decision.BLOCK
    assert "blocked category: Gaming" in result.reasons


def test_blocked_category_matches_name():
    engine = FilteringEngine(FilteringConfig(blocked_categories=["gaming"]))
    result = engine.evaluate_video(candidate(category="20", title="Toy review"))
    assert result.decision == Decision.BLOCK


def test_default_decision_requires_parent_for_unknown_video():
    engine = FilteringEngine(FilteringConfig())
    result = engine.evaluate_video(candidate(title="Random vlog", category="22"))
    assert result.decision == Decision.REQUIRE_PARENT_APPROVAL


def test_allowed_keyword_still_allows_educational_video():
    engine = FilteringEngine(FilteringConfig(allowed_keywords=["science"]))
    result = engine.evaluate_video(candidate(title="Calm science for kids", category="27"))
    assert result.decision == Decision.ALLOW


def test_short_video_requires_parent_before_allowed_keywords():
    engine = FilteringEngine(
        FilteringConfig(
            allowed_keywords=["science"],
            short_video_max_seconds=60,
            short_video_decision="REQUIRE_PARENT_APPROVAL",
        )
    )

    result = engine.evaluate_video(candidate(title="Calm science for kids", duration_seconds=42, category="27"))

    assert result.decision == Decision.REQUIRE_PARENT_APPROVAL
    assert "short video under 60 seconds" in result.reasons


def test_short_video_can_be_configured_to_block():
    engine = FilteringEngine(FilteringConfig(short_video_max_seconds=60, short_video_decision="BLOCK"))

    result = engine.evaluate_video(candidate(title="Plain clip", duration_seconds=59, category="27"))

    assert result.decision == Decision.BLOCK
