from fastapi.testclient import TestClient

from app.main import app


def test_admin_page_loads():
    client = TestClient(app)

    response = client.get("/admin")

    assert response.status_code == 200
    assert "Remote Admin" in response.text
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
    assert "youtube" in payload
    assert "history" in payload
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
