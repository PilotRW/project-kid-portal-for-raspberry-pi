import hashlib
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_kiosk_control_sudoers_is_installed():
    installer = (REPO_ROOT / "deploy/scripts/pi-install.sh").read_text(encoding="utf-8")

    assert "kid-portal-kiosk-control.sh /usr/local/sbin/kid-portal-kiosk-control" in installer
    assert "deploy/sudoers/kid-portal-kiosk-control" in installer
    assert "visudo -cf /etc/sudoers.d/kid-portal-kiosk-control" in installer


def test_network_access_uses_deployed_lan_cidr_file():
    installer = (REPO_ROOT / "deploy/scripts/pi-install.sh").read_text(encoding="utf-8")
    script = (REPO_ROOT / "deploy/scripts/kid-portal-network-access.sh").read_text(encoding="utf-8")

    assert 'printf "%s\\n" "$LAN_CIDR" > "$CONFIG_DIR/lan-cidr"' in installer
    assert 'LAN_CIDR_FILE="/etc/kid-portal/lan-cidr"' in script
    assert 'LAN_CIDR="$(head -n 1 "$LAN_CIDR_FILE")"' in script


def test_youtube_approval_log_is_deployed():
    installer = (REPO_ROOT / "deploy/scripts/pi-install.sh").read_text(encoding="utf-8")

    assert "youtube-approval-log.json" in installer
    assert "KID_PORTAL_YOUTUBE_APPROVAL_LOG" in installer


def test_filter_insights_is_deployed():
    installer = (REPO_ROOT / "deploy/scripts/pi-install.sh").read_text(encoding="utf-8")

    assert "filter-insights.json" in installer
    assert "KID_PORTAL_FILTER_INSIGHTS" in installer


def test_parent_pin_recovery_tool_is_installed_without_web_sudoers():
    installer = (REPO_ROOT / "deploy/scripts/pi-install.sh").read_text(encoding="utf-8")

    assert "kid-portal-reset-parent-pin.py /usr/local/sbin/kid-portal-reset-parent-pin" in installer
    assert "sudoers/kid-portal-reset-parent-pin" not in installer


def test_parent_pin_recovery_tool_updates_config(tmp_path):
    config_path = tmp_path / "config.json"
    view_hash = hashlib.sha256("1357".encode("utf-8")).hexdigest()
    config_path.write_text(json.dumps({"parent": {"pin_sha256": "old", "view_pin_sha256": view_hash}}), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "deploy/scripts/kid-portal-reset-parent-pin.py"), "2468", str(config_path)],
        check=False,
        text=True,
        capture_output=True,
    )

    data = json.loads(config_path.read_text(encoding="utf-8"))
    assert result.returncode == 0
    assert data["parent"]["pin_sha256"] == hashlib.sha256("2468".encode("utf-8")).hexdigest()
    assert data["parent"]["view_pin_sha256"] == view_hash


def test_parent_pin_recovery_tool_rejects_viewing_pin(tmp_path):
    config_path = tmp_path / "config.json"
    view_hash = hashlib.sha256("1357".encode("utf-8")).hexdigest()
    config_path.write_text(json.dumps({"parent": {"pin_sha256": "old", "view_pin_sha256": view_hash}}), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "deploy/scripts/kid-portal-reset-parent-pin.py"), "1357", str(config_path)],
        check=False,
        text=True,
        capture_output=True,
    )

    data = json.loads(config_path.read_text(encoding="utf-8"))
    assert result.returncode == 2
    assert data["parent"]["pin_sha256"] == "old"
    assert "different from viewing PIN" in result.stderr


def test_keyboard_is_centered_against_kiosk_stage():
    styles = (REPO_ROOT / "app/static/styles.css").read_text(encoding="utf-8")

    assert "inset-inline: max(0px, calc((100vw - var(--stage-width)) / 2));" in styles
    assert "transform: none;" in styles
