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
