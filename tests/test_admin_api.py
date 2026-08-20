from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app
from app.services.display_manager import DisplayStatus
from app.services.filtering_engine import VideoCandidate
from app.services.usage_tracker import UsageTrackerService
from app.services.wifi_manager import WifiConnectResult, WifiNetwork, WifiStatus
from app.services.youtube_key_manager import YouTubeKeyUpdateResult


def setup_function():
    main_module.admin_pin_attempts.clear()
    main_module.approved_youtube_videos.clear()


class FakeYouTubeLookup:
    def __init__(self, candidates):
        self.candidates = candidates

    async def get_video(self, video_id):
        return self.candidates.get(video_id)


class FakeApprovalLog:
    def __init__(self):
        self.entries = []

    def add(self, evaluated):
        self.entries.append(evaluated)

    def list_entries(self):
        return self.entries


class FakeFilterInsights:
    def __init__(self):
        self.gaps = []
        self.approvals = []

    def record_gap(self, channel_title, title):
        self.gaps.append((channel_title, title))

    def record_approval(self, channel_title, title):
        self.approvals.append((channel_title, title))

    def top(self, kind=None):
        return []


def video_candidate(video_id: str, title: str = "Science lesson for kids") -> VideoCandidate:
    return VideoCandidate(
        video_id=video_id,
        title=title,
        description="A calm educational video.",
        channel_id="safe-channel",
        channel_title="Safe Learning",
        category="27",
        duration_seconds=600,
    )


def test_admin_page_loads():
    client = TestClient(app)

    response = client.get("/admin")

    assert response.status_code == 200
    assert "Settings" in response.text
    assert "/static/admin.js" in response.text


def test_admin_state_rejects_invalid_pin():
    client = TestClient(app)

    response = client.post("/api/admin/state", json={"pin": "0000"})

    assert response.status_code == 403


def test_admin_pin_lockout_after_repeated_failures(monkeypatch):
    monkeypatch.setattr(main_module, "ADMIN_PIN_MAX_ATTEMPTS", 2)
    monkeypatch.setattr(main_module, "ADMIN_PIN_FINDTIME_SECONDS", 600)
    monkeypatch.setattr(main_module, "ADMIN_PIN_LOCKOUT_SECONDS", 600)
    client = TestClient(app)

    first = client.post("/api/admin/state", json={"pin": "0000"})
    second = client.post("/api/admin/state", json={"pin": "0000"})
    locked = client.post("/api/admin/state", json={"pin": "1234"})

    assert first.status_code == 403
    assert second.status_code == 403
    assert locked.status_code == 429
    assert "Retry-After" in locked.headers


def test_admin_state_accepts_parent_pin_without_exposing_key():
    client = TestClient(app)

    response = client.post("/api/admin/state", json={"pin": "1234"})

    assert response.status_code == 200
    payload = response.json()
    assert "config" in payload
    assert "network" in payload
    assert "storage" in payload
    assert "monitoring" in payload
    assert "youtube" in payload
    assert "history" in payload
    assert "approvals" in payload
    assert "usage" in payload
    assert "network_access" in payload
    assert "api_key" not in payload["youtube"]


def test_parent_storage_requires_valid_pin():
    client = TestClient(app)

    rejected = client.post("/api/parent/storage", json={"pin": "0000"})
    accepted = client.post("/api/parent/storage", json={"pin": "1234"})

    assert rejected.status_code == 403
    assert accepted.status_code == 200
    payload = accepted.json()
    assert payload["path"] == "/"
    assert payload["total_bytes"] >= payload["free_bytes"]
    assert payload["percent_used"] >= 0


def test_parent_monitoring_requires_valid_pin():
    client = TestClient(app)

    rejected = client.post("/api/parent/monitoring", json={"pin": "0000"})
    accepted = client.post("/api/parent/monitoring", json={"pin": "1234"})

    assert rejected.status_code == 403
    assert accepted.status_code == 200
    payload = accepted.json()
    assert "top_processes" in payload
    assert "hottest_process" in payload
    assert "temperature_c" in payload
    assert "throttled_state" in payload


def test_terminal_controls_are_pin_protected():
    client = TestClient(app)

    terminal = client.post("/api/parent/terminal/start", json={"pin": "0000"})
    kiosk = client.post("/api/parent/kiosk/start", json={"pin": "0000"})

    assert terminal.status_code == 403
    assert kiosk.status_code == 403


def test_terminal_controls_use_kiosk_control_wrapper(monkeypatch):
    actions = []

    def fake_kiosk_control(action):
        actions.append(action)

    monkeypatch.setattr(main_module, "run_kiosk_control", fake_kiosk_control)
    client = TestClient(app)

    terminal = client.post("/api/parent/terminal/start", json={"pin": "1234"})
    kiosk = client.post("/api/parent/kiosk/start", json={"pin": "1234"})

    assert terminal.status_code == 200
    assert kiosk.status_code == 200
    assert actions == ["terminal", "kiosk"]


def test_kiosk_settings_include_debug_terminal_controls():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "exit-to-terminal" in response.text
    assert "return-to-kiosk" in response.text
    assert "refresh-monitoring" in response.text
    assert "view-approval-form" in response.text
    assert "view-pin" in response.text
    assert "wifi-form" in response.text
    assert "scan-wifi" in response.text
    assert "display-mode" in response.text
    assert "apply-display-mode" in response.text
    assert 'id="keyboard"' in response.text
    assert "app.js?v=20260820-04" in response.text


def test_remote_admin_includes_viewing_pin_control():
    client = TestClient(app)

    response = client.get("/admin")

    assert response.status_code == 200
    assert "Viewing PIN" in response.text
    assert "view-pin" in response.text
    assert "Time Limits" in response.text
    assert "YouTube Search" in response.text
    assert "YouTube API Key" in response.text
    assert "youtube-key-form" in response.text
    assert "Short video threshold" in response.text
    assert "Parent Approval Log" in response.text
    assert "Unmatched" in response.text
    assert "Default-Allow Gaps" in response.text
    assert "tab-nav" in response.text
    assert "Blocked Categories" in response.text
    assert "Debug Terminal" in response.text
    assert "Raspberry Pi Software" in response.text
    assert "update-system-software" in response.text
    assert "Display" in response.text
    assert "display-mode" in response.text
    assert "Sign out" in response.text
    assert "lock-admin" not in response.text
    assert "content-lan-toggle" in response.text
    assert "content-lan-url" in response.text
    assert "data-rule-filter=\"blocked_keywords\"" in response.text
    assert "data-rule-count=\"blocked_keywords\"" in response.text
    assert "admin.css?v=20260715-01" in response.text
    assert "admin.js?v=20260820-05" in response.text


def test_admin_surface_uses_admin_as_default(monkeypatch):
    monkeypatch.setenv("KID_PORTAL_SURFACE", "admin")
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "Settings" in response.text
    assert "login-form" in response.text


def test_admin_surface_blocks_content_routes(monkeypatch):
    monkeypatch.setenv("KID_PORTAL_SURFACE", "admin")
    client = TestClient(app)

    response = client.get("/youtube/watch/video-123")

    assert response.status_code == 404


def test_network_access_update_requires_valid_pin():
    client = TestClient(app)

    response = client.post("/api/parent/network-access", json={"pin": "0000", "enabled": True})

    assert response.status_code == 403


def test_display_update_requires_valid_pin():
    client = TestClient(app)

    response = client.post("/api/parent/display", json={"pin": "0000", "mode": "4k"})

    assert response.status_code == 403


def test_display_update_saves_and_applies(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(main_module.config_service.load().model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(main_module.config_service, "config_path", config_path)

    class FakeDisplayManager:
        def apply(self, mode):
            assert mode == "4k"
            return DisplayStatus(configured_mode=mode, current_resolution="3840x2160")

    monkeypatch.setattr(main_module, "display_manager", FakeDisplayManager())
    client = TestClient(app)

    response = client.post("/api/parent/display", json={"pin": "1234", "mode": "4k"})

    assert response.status_code == 200
    assert response.json()["current_resolution"] == "3840x2160"
    assert main_module.config_service.load().display.mode == "4k"


def test_display_update_rejects_unknown_mode():
    client = TestClient(app)

    response = client.post("/api/parent/display", json={"pin": "1234", "mode": "720p"})

    assert response.status_code == 400


def test_software_update_requires_valid_pin(monkeypatch):
    called = []

    def fake_update():
        called.append(True)

    monkeypatch.setattr(main_module, "run_software_update", fake_update)
    client = TestClient(app)

    rejected = client.post("/api/parent/software/update", json={"pin": "0000"})
    accepted = client.post("/api/parent/software/update", json={"pin": "1234"})

    assert rejected.status_code == 403
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "software_update_started"
    assert called == [True]


def test_youtube_key_update_requires_valid_pin():
    client = TestClient(app)

    response = client.put("/api/parent/youtube/key", json={"pin": "0000", "api_key": "A" * 30})

    assert response.status_code == 403


def test_youtube_key_update_saves_without_exposing_key(monkeypatch):
    class FakeYouTubeKeyManager:
        def set_key(self, api_key):
            assert api_key == "A" * 30
            return YouTubeKeyUpdateResult(status="saved")

    class FakeYouTubeService:
        def status(self):
            return {"configured": True, "mode": "live", "source": "/etc/kid-portal/youtube-api-key.txt"}

    class FakeSearchCache:
        def __init__(self):
            self.cleared = False

        def clear(self):
            self.cleared = True

    cache = FakeSearchCache()
    monkeypatch.setattr(main_module, "youtube_key_manager", FakeYouTubeKeyManager())
    monkeypatch.setattr(main_module, "youtube_service", FakeYouTubeService())
    monkeypatch.setattr(main_module, "youtube_search_cache_service", cache)
    client = TestClient(app)

    response = client.put("/api/parent/youtube/key", json={"pin": "1234", "api_key": "A" * 30})

    assert response.status_code == 200
    payload = response.json()
    assert payload["youtube"]["configured"] is True
    assert "api_key" not in payload
    assert "A" * 30 not in response.text
    assert cache.cleared is True


def test_youtube_key_update_rejects_short_key():
    client = TestClient(app)

    response = client.put("/api/parent/youtube/key", json={"pin": "1234", "api_key": "short"})

    assert response.status_code == 400


def test_youtube_key_clear_uses_pin(monkeypatch):
    class FakeYouTubeKeyManager:
        def clear_key(self):
            return YouTubeKeyUpdateResult(status="cleared")

    class FakeYouTubeService:
        def status(self):
            return {"configured": False, "mode": "demo", "source": "none"}

    class FakeSearchCache:
        def __init__(self):
            self.cleared = False

        def clear(self):
            self.cleared = True

    cache = FakeSearchCache()
    monkeypatch.setattr(main_module, "youtube_key_manager", FakeYouTubeKeyManager())
    monkeypatch.setattr(main_module, "youtube_service", FakeYouTubeService())
    monkeypatch.setattr(main_module, "youtube_search_cache_service", cache)
    client = TestClient(app)

    response = client.request("DELETE", "/api/parent/youtube/key", json={"pin": "1234"})

    assert response.status_code == 200
    assert response.json()["youtube"]["mode"] == "demo"
    assert cache.cleared is True


def test_wifi_controls_require_valid_pin():
    client = TestClient(app)

    response = client.post("/api/parent/wifi/scan", json={"pin": "0000"})

    assert response.status_code == 403


def test_wifi_scan_returns_networks(monkeypatch):
    class FakeWifiManager:
        def scan(self):
            return [WifiNetwork(ssid="Home", signal=90, security="WPA2", connected=True)]

    monkeypatch.setattr(main_module, "wifi_manager", FakeWifiManager())
    client = TestClient(app)

    response = client.post("/api/parent/wifi/scan", json={"pin": "1234"})

    assert response.status_code == 200
    assert response.json()["networks"][0]["ssid"] == "Home"


def test_wifi_connect_uses_pin(monkeypatch):
    class FakeWifiManager:
        def connect(self, ssid, password=None):
            assert ssid == "Home"
            assert password == "secret"
            return WifiConnectResult(status="connecting", message="ok")

    monkeypatch.setattr(main_module, "wifi_manager", FakeWifiManager())
    client = TestClient(app)

    response = client.post("/api/parent/wifi/connect", json={"pin": "1234", "ssid": "Home", "password": "secret"})

    assert response.status_code == 200
    assert response.json()["status"] == "connecting"


def test_wifi_status_uses_pin(monkeypatch):
    class FakeWifiManager:
        def status(self):
            return WifiStatus(state="100 (connected)", connection="Home")

    monkeypatch.setattr(main_module, "wifi_manager", FakeWifiManager())
    client = TestClient(app)

    response = client.post("/api/parent/wifi/status", json={"pin": "1234"})

    assert response.status_code == 200
    assert response.json()["connection"] == "Home"


def test_youtube_approval_uses_separate_viewing_pin(monkeypatch):
    approval_log = FakeApprovalLog()
    insights = FakeFilterInsights()
    monkeypatch.setattr(main_module, "youtube_service", FakeYouTubeLookup({"abc123": video_candidate("abc123")}))
    monkeypatch.setattr(main_module, "youtube_approval_log_service", approval_log)
    monkeypatch.setattr(main_module, "filter_insights_service", insights)
    client = TestClient(app)

    parent_pin = client.post("/api/youtube/approval/unlock", json={"pin": "1234", "video_id": "abc123"})
    view_pin = client.post("/api/youtube/approval/unlock", json={"pin": "4321", "video_id": "abc123"})

    assert parent_pin.status_code == 403
    assert view_pin.status_code == 200
    assert view_pin.json()["watch_url"] == "/youtube/watch/abc123"
    assert [entry.video.video_id for entry in approval_log.entries] == ["abc123"]
    assert insights.approvals == [("Safe Learning", "Science lesson for kids")]


def test_admin_history_clear_requires_valid_pin():
    client = TestClient(app)

    response = client.post("/api/admin/youtube/history/clear", json={"pin": "0000"})

    assert response.status_code == 403


def test_public_history_delete_requires_valid_pin():
    client = TestClient(app)

    missing_pin = client.delete("/api/youtube/history")
    invalid_pin = client.request("DELETE", "/api/youtube/history", json={"pin": "0000"})

    assert missing_pin.status_code == 422
    assert invalid_pin.status_code == 403


def test_thumbnail_proxy_rejects_unapproved_hosts():
    client = TestClient(app)

    response = client.get("/api/youtube/thumbnail", params={"url": "https://example.com/image.jpg"})

    assert response.status_code == 400


def test_watch_page_sandboxes_youtube_embed(monkeypatch):
    monkeypatch.setattr(main_module, "youtube_service", FakeYouTubeLookup({"video-123": video_candidate("video-123")}))
    client = TestClient(app)

    response = client.get("/youtube/watch/video-123")

    assert response.status_code == 200
    assert "sandbox=\"allow-scripts allow-same-origin allow-presentation\"" in response.text
    assert "allowfullscreen" in response.text
    assert "fs=1" in response.text
    assert "enablejsapi=1" in response.text
    assert "guardCurrentVideo" in response.text
    assert "/api/usage/playback/heartbeat" in response.text


def test_watch_page_blocks_filtered_video(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "youtube_service",
        FakeYouTubeLookup({"video-123": video_candidate("video-123", title="Extreme prank challenge")}),
    )
    client = TestClient(app)

    response = client.get("/youtube/watch/video-123")

    assert response.status_code == 200
    assert "This video is blocked by Kid Portal filters." in response.text
    assert "youtube-nocookie.com/embed/video-123" not in response.text


def test_watch_page_requires_parent_approval_for_default_decision(monkeypatch):
    approval_log = FakeApprovalLog()
    insights = FakeFilterInsights()
    monkeypatch.setattr(
        main_module,
        "youtube_service",
        FakeYouTubeLookup(
            {
                "unknown-123": VideoCandidate(
                    video_id="unknown-123",
                    title="Plain cartoon",
                    description="",
                    channel_id="plain-channel",
                    channel_title="Plain Channel",
                    category=None,
                    duration_seconds=600,
                )
            }
        ),
    )
    monkeypatch.setattr(main_module, "youtube_approval_log_service", approval_log)
    monkeypatch.setattr(main_module, "filter_insights_service", insights)
    client = TestClient(app)

    direct = client.get("/youtube/watch/unknown-123")
    unlocked = client.post("/api/youtube/approval/unlock", json={"pin": "4321", "video_id": "unknown-123"})
    approved = client.get("/youtube/watch/unknown-123")

    assert direct.status_code == 200
    assert "Parent approval is required for this video." in direct.text
    assert unlocked.status_code == 200
    assert approved.status_code == 200
    assert "youtube-nocookie.com/embed/unknown-123" in approved.text


def test_playback_usage_api_tracks_active_play(tmp_path, monkeypatch):
    monkeypatch.setattr(main_module, "usage_tracker_service", UsageTrackerService(tmp_path / "usage.json"))
    client = TestClient(app)

    started = client.post("/api/usage/playback/start", json={"video_id": "video-123"})

    assert started.status_code == 200
    session_id = started.json()["session_id"]
    heartbeat = client.post(
        "/api/usage/playback/heartbeat",
        json={"session_id": session_id, "state": "playing"},
    )
    stopped = client.post("/api/usage/playback/stop", json={"session_id": session_id})

    assert heartbeat.status_code == 200
    assert "usage" in heartbeat.json()
    assert stopped.status_code == 200
