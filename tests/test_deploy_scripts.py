import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_kiosk_control_sudoers_is_installed():
    installer = (REPO_ROOT / "deploy/scripts/pi-install.sh").read_text(encoding="utf-8")
    sudoers = (REPO_ROOT / "deploy/sudoers/kid-portal-kiosk-control").read_text(encoding="utf-8")
    kiosk_control = (REPO_ROOT / "deploy/scripts/kid-portal-kiosk-control.sh").read_text(encoding="utf-8")

    assert "kid-portal-kiosk-control.sh /usr/local/sbin/kid-portal-kiosk-control" in installer
    assert "kid-portal-launch-chromium.sh /usr/local/sbin/kid-portal-launch-chromium" in installer
    assert "deploy/sudoers/kid-portal-kiosk-control" in installer
    assert "visudo -cf /etc/sudoers.d/kid-portal-kiosk-control" in installer
    assert "/usr/local/sbin/kid-portal-kiosk-control restart-kiosk" in sudoers
    assert "/usr/local/sbin/kid-portal-kiosk-control reboot" in sudoers
    assert "systemctl stop kid-portal-kiosk.service" in kiosk_control
    assert "systemctl restart kid-portal-x.service" in kiosk_control
    assert "systemctl start kid-portal-kiosk.service" in kiosk_control


def test_chromium_launcher_pins_window_to_active_display():
    launcher = (REPO_ROOT / "deploy/scripts/kid-portal-launch-chromium.sh").read_text(encoding="utf-8")
    service = (REPO_ROOT / "deploy/systemd/kid-portal-kiosk.service").read_text(encoding="utf-8")
    x_service = (REPO_ROOT / "deploy/systemd/kid-portal-x.service").read_text(encoding="utf-8")

    assert "kid-portal-display-mode" in launcher
    assert "--window-position=0,0" in launcher
    assert '--window-size="${WIDTH},${HEIGHT}"' in launcher
    assert "--start-fullscreen" in launcher
    assert "ExecStart=/usr/local/sbin/kid-portal-launch-chromium" in service
    assert "TimeoutStopSec=3" in x_service


def test_remote_control_dependency_is_installed():
    installer = (REPO_ROOT / "deploy/scripts/pi-install.sh").read_text(encoding="utf-8")

    assert "xdotool" in installer


def test_tailscale_bootstrap_is_opt_in_and_interface_scoped():
    installer = (REPO_ROOT / "deploy/scripts/pi-install.sh").read_text(encoding="utf-8")
    bootstrap = (REPO_ROOT / "deploy/bootstrap-pi.sh").read_text(encoding="utf-8")
    deploy = (REPO_ROOT / "deploy/deploy-to-pi.sh").read_text(encoding="utf-8")

    assert 'ENABLE_TAILSCALE="${KID_PORTAL_ENABLE_TAILSCALE:-0}"' in installer
    assert "https://tailscale.com/install.sh" in installer
    assert '--auth-key "$TAILSCALE_AUTHKEY"' in installer
    assert "--accept-dns=false" in installer
    assert 'ufw allow in on tailscale0 from "$MANAGEMENT_CIDR" to any port 22 proto tcp' in installer
    assert 'ufw allow in on tailscale0 from "$MANAGEMENT_CIDR" to any port 80 proto tcp' in installer
    assert 'ALLOW_LAN_SSH="${KID_PORTAL_ALLOW_LAN_SSH:-1}"' in installer
    assert "KID_PORTAL_ENABLE_TAILSCALE" in bootstrap
    assert "KID_PORTAL_ENABLE_TAILSCALE" in deploy


def test_fleet_inventory_template_keeps_auth_keys_out_of_git():
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    example = (REPO_ROOT / "deploy/devices.example.json").read_text(encoding="utf-8")
    data = json.loads(example)

    assert ".local/" in gitignore
    assert "tailscale_authkey_env" in example
    assert "tskey-" not in example
    assert data["defaults"]["enable_tailscale"] is True
    assert data["defaults"]["allow_lan_ssh"] is True


def test_fleet_runner_lists_example_inventory():
    env = os.environ.copy()
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "deploy/fleet.py"),
            "list",
            "--inventory",
            str(REPO_ROOT / "deploy/devices.example.json"),
        ],
        check=False,
        text=True,
        capture_output=True,
        env=env,
    )

    assert result.returncode == 0
    assert "home" in result.stdout
    assert "family-1" in result.stdout
    assert "tailscale=1" in result.stdout


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


def test_software_update_log_is_readable_by_portal_user():
    script = (REPO_ROOT / "deploy/scripts/kid-portal-software-update.sh").read_text(encoding="utf-8")
    installer = (REPO_ROOT / "deploy/scripts/pi-install.sh").read_text(encoding="utf-8")
    checker = (REPO_ROOT / "deploy/check-pi.sh").read_text(encoding="utf-8")

    assert 'chown root:pi "$LOG_FILE"' in script
    assert 'chmod 640 "$LOG_FILE"' in script
    assert 'REQUEST_FILE="/run/kid-portal/software-update.request"' in script
    assert 'rm -f "$REQUEST_FILE"' in script
    assert "kid-portal-software-update.path" in installer
    assert "kid-portal-software-update.path" in checker


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


def test_parent_pin_recovery_tool_rejects_remote_pin(tmp_path):
    config_path = tmp_path / "config.json"
    remote_hash = hashlib.sha256("2580".encode("utf-8")).hexdigest()
    config_path.write_text(json.dumps({"parent": {"pin_sha256": "old", "remote_pin_sha256": remote_hash}}), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "deploy/scripts/kid-portal-reset-parent-pin.py"), "2580", str(config_path)],
        check=False,
        text=True,
        capture_output=True,
    )

    data = json.loads(config_path.read_text(encoding="utf-8"))
    assert result.returncode == 2
    assert data["parent"]["pin_sha256"] == "old"
    assert "different from remote PIN" in result.stderr


def test_keyboard_is_centered_against_kiosk_stage():
    styles = (REPO_ROOT / "app/static/styles.css").read_text(encoding="utf-8")

    assert "inset-inline: max(0px, calc((100vw - var(--stage-width)) / 2));" in styles
    assert "transform: none;" in styles


def test_kiosk_disables_back_forward_cache_for_external_media():
    launcher = (REPO_ROOT / "deploy/scripts/kid-portal-launch-chromium.sh").read_text(encoding="utf-8")

    assert "--disable-features=Translate,DesktopPWAsTabStrip,BackForwardCache" in launcher


def test_keyboard_preview_masks_password_inputs():
    script = (REPO_ROOT / "app/static/app.js").read_text(encoding="utf-8")

    assert "function keyboardPreviewText(input)" in script
    assert 'input.type === "password"' in script
    assert 'return "•".repeat(input.value.length);' in script


def test_kiosk_uses_spatial_arrow_navigation():
    script = (REPO_ROOT / "app/static/app.js").read_text(encoding="utf-8")

    assert "function moveFocusDirection(direction)" in script
    assert "function directionalScore(direction, current, candidate)" in script
    assert "moveFocusDirection(event.key.replace(\"Arrow\", \"\").toLowerCase())" in script


def test_kiosk_scrolls_to_focused_remote_target():
    script = (REPO_ROOT / "app/static/app.js").read_text(encoding="utf-8")

    assert "function ensureFocusVisible(target)" in script
    assert 'const shell = document.querySelector(".shell");' in script
    assert 'target.focus({ preventScroll: true });' in script
    assert "ensureFocusVisible(target);" in script
    assert "shell.scrollBy" in script
