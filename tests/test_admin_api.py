from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app
from app.services.usage_tracker import UsageTrackerService


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


def test_kiosk_settings_include_debug_terminal_controls():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "exit-to-terminal" in response.text
    assert "return-to-kiosk" in response.text
    assert "refresh-monitoring" in response.text
    assert "view-approval-form" in response.text
    assert "view-pin" in response.text


def test_remote_admin_includes_viewing_pin_control():
    client = TestClient(app)

    response = client.get("/admin")

    assert response.status_code == 200
    assert "Viewing PIN" in response.text
    assert "view-pin" in response.text
    assert "Time Limits" in response.text
    assert "YouTube Search" in response.text
    assert "tab-nav" in response.text
    assert "Blocked Categories" in response.text
    assert "Debug Terminal" in response.text
    assert "content-lan-toggle" in response.text


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


def test_youtube_approval_uses_separate_viewing_pin():
    client = TestClient(app)

    parent_pin = client.post("/api/youtube/approval/unlock", json={"pin": "1234", "video_id": "abc123"})
    view_pin = client.post("/api/youtube/approval/unlock", json={"pin": "4321", "video_id": "abc123"})

    assert parent_pin.status_code == 403
    assert view_pin.status_code == 200
    assert view_pin.json()["watch_url"] == "/youtube/watch/abc123"


def test_admin_history_clear_requires_valid_pin():
    client = TestClient(app)

    response = client.post("/api/admin/youtube/history/clear", json={"pin": "0000"})

    assert response.status_code == 403


def test_thumbnail_proxy_rejects_unapproved_hosts():
    client = TestClient(app)

    response = client.get("/api/youtube/thumbnail", params={"url": "https://example.com/image.jpg"})

    assert response.status_code == 400


def test_watch_page_sandboxes_youtube_embed():
    client = TestClient(app)

    response = client.get("/youtube/watch/video-123")

    assert response.status_code == 200
    assert "sandbox=\"allow-scripts allow-same-origin allow-presentation\"" in response.text
    assert "allowfullscreen" in response.text
    assert "fs=1" in response.text
    assert "enablejsapi=1" in response.text
    assert "guardCurrentVideo" in response.text
    assert "/api/usage/playback/heartbeat" in response.text


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
