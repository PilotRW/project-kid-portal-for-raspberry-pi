#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="${1:-$(pwd)}"
APP_DIR="${KID_PORTAL_APP_DIR:-/opt/kid-portal}"
CONFIG_DIR="${KID_PORTAL_CONFIG_DIR:-/etc/kid-portal}"
LAN_CIDR="${KID_PORTAL_LAN_CIDR:-192.168.0.0/24}"
MANAGEMENT_CIDR="${KID_PORTAL_MANAGEMENT_CIDR:-}"
ALLOW_LAN_SSH="${KID_PORTAL_ALLOW_LAN_SSH:-1}"
PI_USER="${KID_PORTAL_USER:-pi}"
SKIP_APT="${KID_PORTAL_SKIP_APT:-0}"
ENABLE_ZEROTIER="${KID_PORTAL_ENABLE_ZEROTIER:-0}"
ZEROTIER_NETWORK_ID="${KID_PORTAL_ZEROTIER_NETWORK_ID:-}"
ZEROTIER_INTERFACE=""

write_chromium_policy() {
  local tmp_file
  tmp_file="$(mktemp)"
  for _ in $(seq 1 30); do
    if curl -fsS http://127.0.0.1:8080/api/policies/chromium > "$tmp_file" \
      && python3 -m json.tool "$tmp_file" >/dev/null; then
      install -m 644 "$tmp_file" /etc/chromium/policies/managed/kid-portal.json
      rm -f "$tmp_file"
      return 0
    fi
    sleep 1
  done
  rm -f "$tmp_file"
  echo "Kid Portal API did not return a valid Chromium policy." >&2
  return 1
}

configure_zerotier() {
  if [[ "$ENABLE_ZEROTIER" != "1" ]]; then
    return 0
  fi

  if ! command -v zerotier-cli >/dev/null 2>&1; then
    curl -sSf https://install.zerotier.com | bash
  fi

  systemctl enable --now zerotier-one

  if [[ -z "$ZEROTIER_NETWORK_ID" ]]; then
    echo "ZeroTier installed. Set KID_PORTAL_ZEROTIER_NETWORK_ID to join the private management network." >&2
    return 0
  fi

  if [[ ! "$ZEROTIER_NETWORK_ID" =~ ^[0-9a-fA-F]{16}$ ]]; then
    echo "Invalid ZeroTier network ID: expected 16 hexadecimal characters." >&2
    exit 2
  fi

  zerotier-cli join "$ZEROTIER_NETWORK_ID"
  ZEROTIER_INTERFACE="$(zerotier-cli -j listnetworks | python3 -c '
import json
import sys

network_id = sys.argv[1].lower()
for network in json.load(sys.stdin):
    if str(network.get("nwid", "")).lower() == network_id:
        print(network.get("portDeviceName", ""))
        break
' "$ZEROTIER_NETWORK_ID")"
}

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run with sudo/root." >&2
  exit 2
fi

if [[ ! -f "$SOURCE_DIR/pyproject.toml" || ! -d "$SOURCE_DIR/app" ]]; then
  echo "Source directory does not look like Kid Portal: $SOURCE_DIR" >&2
  exit 2
fi

if ! id "$PI_USER" >/dev/null 2>&1; then
  echo "Expected user does not exist: $PI_USER" >&2
  exit 2
fi

if [[ "$SKIP_APT" != "1" ]]; then
  apt-get update
  apt-get install -y \
    chromium-browser \
    fail2ban \
    keyd \
    iw \
    network-manager \
    openbox \
    python3-pip \
    python3-venv \
    rsync \
    ufw \
    unclutter \
    xdotool \
    xinit \
    xserver-xorg
fi

install -d -m 755 -o "$PI_USER" -g "$PI_USER" "$APP_DIR"
rsync -a --delete \
  --exclude ".git/" \
  --exclude ".pytest_cache/" \
  --exclude ".venv/" \
  --exclude "__pycache__/" \
  "$SOURCE_DIR/" "$APP_DIR/"
chown -R "$PI_USER:$PI_USER" "$APP_DIR"

install -d -m 755 "$CONFIG_DIR" /etc/chromium/policies/managed /etc/X11/xorg.conf.d /etc/sudoers.d
install -d -m 755 /etc/NetworkManager/conf.d /etc/systemd/journald.conf.d /var/log/journal
printf "%s\n" "$LAN_CIDR" > "$CONFIG_DIR/lan-cidr"
chown root:root "$CONFIG_DIR/lan-cidr"
chmod 644 "$CONFIG_DIR/lan-cidr"
if [[ ! -f "$CONFIG_DIR/config.json" ]]; then
  install -m 664 -o root -g "$PI_USER" "$APP_DIR/config/kid-portal.json" "$CONFIG_DIR/config.json"
else
  chown root:"$PI_USER" "$CONFIG_DIR/config.json"
  chmod 664 "$CONFIG_DIR/config.json"
fi

touch "$CONFIG_DIR/search-history.json" "$CONFIG_DIR/youtube-search-cache.json" "$CONFIG_DIR/youtube-approval-log.json" "$CONFIG_DIR/youtube-blocked-log.json" "$CONFIG_DIR/filter-insights.json" "$CONFIG_DIR/usage.json"
chown "$PI_USER:$PI_USER" "$CONFIG_DIR/search-history.json" "$CONFIG_DIR/youtube-search-cache.json" "$CONFIG_DIR/youtube-approval-log.json" "$CONFIG_DIR/youtube-blocked-log.json" "$CONFIG_DIR/filter-insights.json" "$CONFIG_DIR/usage.json"
chmod 600 "$CONFIG_DIR/youtube-search-cache.json" "$CONFIG_DIR/youtube-approval-log.json" "$CONFIG_DIR/youtube-blocked-log.json" "$CONFIG_DIR/filter-insights.json" "$CONFIG_DIR/usage.json"

if [[ ! -f "$CONFIG_DIR/youtube.env" ]]; then
  cat > "$CONFIG_DIR/youtube.env" <<EOF
YOUTUBE_API_KEY_FILE=$CONFIG_DIR/youtube-api-key.txt
KID_PORTAL_SEARCH_HISTORY=$CONFIG_DIR/search-history.json
KID_PORTAL_YOUTUBE_SEARCH_CACHE=$CONFIG_DIR/youtube-search-cache.json
KID_PORTAL_YOUTUBE_APPROVAL_LOG=$CONFIG_DIR/youtube-approval-log.json
KID_PORTAL_YOUTUBE_BLOCKED_LOG=$CONFIG_DIR/youtube-blocked-log.json
KID_PORTAL_FILTER_INSIGHTS=$CONFIG_DIR/filter-insights.json
KID_PORTAL_USAGE=$CONFIG_DIR/usage.json
EOF
  chmod 600 "$CONFIG_DIR/youtube.env"
fi
if ! grep -q '^KID_PORTAL_YOUTUBE_APPROVAL_LOG=' "$CONFIG_DIR/youtube.env"; then
  printf '\nKID_PORTAL_YOUTUBE_APPROVAL_LOG=%s/youtube-approval-log.json\n' "$CONFIG_DIR" >> "$CONFIG_DIR/youtube.env"
fi
if ! grep -q '^KID_PORTAL_YOUTUBE_BLOCKED_LOG=' "$CONFIG_DIR/youtube.env"; then
  printf '\nKID_PORTAL_YOUTUBE_BLOCKED_LOG=%s/youtube-blocked-log.json\n' "$CONFIG_DIR" >> "$CONFIG_DIR/youtube.env"
fi
if ! grep -q '^KID_PORTAL_FILTER_INSIGHTS=' "$CONFIG_DIR/youtube.env"; then
  printf '\nKID_PORTAL_FILTER_INSIGHTS=%s/filter-insights.json\n' "$CONFIG_DIR" >> "$CONFIG_DIR/youtube.env"
fi

if [[ ! -f "$CONFIG_DIR/youtube-api-key.txt" ]]; then
  install -m 640 -o root -g "$PI_USER" /dev/null "$CONFIG_DIR/youtube-api-key.txt"
fi

cd "$APP_DIR"
if [[ ! -x .venv/bin/python ]]; then
  sudo -u "$PI_USER" python3 -m venv .venv
fi
sudo -u "$PI_USER" .venv/bin/pip install --upgrade pip
sudo -u "$PI_USER" .venv/bin/pip install -e .

cp deploy/systemd/*.service /etc/systemd/system/
cp deploy/systemd/*.path /etc/systemd/system/
cp deploy/systemd/*.timer /etc/systemd/system/
cp deploy/tmpfiles/kid-portal.conf /etc/tmpfiles.d/kid-portal.conf
install -m 644 deploy/networkmanager/99-kid-portal-wifi.conf /etc/NetworkManager/conf.d/99-kid-portal-wifi.conf
install -m 644 deploy/journald/99-kid-portal.conf /etc/systemd/journald.conf.d/99-kid-portal.conf
systemd-tmpfiles --create /etc/tmpfiles.d/kid-portal.conf

install -m 755 deploy/scripts/kid-portal-network-access.sh /usr/local/sbin/kid-portal-network-access
install -m 755 deploy/scripts/kid-portal-display-mode.sh /usr/local/sbin/kid-portal-display-mode
install -m 755 deploy/scripts/kid-portal-launch-chromium.sh /usr/local/sbin/kid-portal-launch-chromium
install -m 755 deploy/scripts/kid-portal-wifi.sh /usr/local/sbin/kid-portal-wifi
install -m 755 deploy/scripts/kid-portal-youtube-key.sh /usr/local/sbin/kid-portal-youtube-key
install -m 755 deploy/scripts/kid-portal-software-update.sh /usr/local/sbin/kid-portal-software-update
install -m 755 deploy/scripts/kid-portal-kiosk-control.sh /usr/local/sbin/kid-portal-kiosk-control
install -m 755 deploy/scripts/kid-portal-wifi-watchdog.sh /usr/local/sbin/kid-portal-wifi-watchdog
install -m 755 deploy/scripts/kid-portal-reset-parent-pin.py /usr/local/sbin/kid-portal-reset-parent-pin
install -m 755 deploy/scripts/kid-portal-zerotier-status.sh /usr/local/sbin/kid-portal-zerotier-status
install -m 440 deploy/sudoers/kid-portal-wifi /etc/sudoers.d/kid-portal-wifi
install -m 440 deploy/sudoers/kid-portal-youtube-key /etc/sudoers.d/kid-portal-youtube-key
install -m 440 deploy/sudoers/kid-portal-software-update /etc/sudoers.d/kid-portal-software-update
install -m 440 deploy/sudoers/kid-portal-kiosk-control /etc/sudoers.d/kid-portal-kiosk-control
install -m 440 deploy/sudoers/kid-portal-health-check /etc/sudoers.d/kid-portal-health-check
visudo -cf /etc/sudoers.d/kid-portal-wifi
visudo -cf /etc/sudoers.d/kid-portal-youtube-key
visudo -cf /etc/sudoers.d/kid-portal-software-update
visudo -cf /etc/sudoers.d/kid-portal-kiosk-control
visudo -cf /etc/sudoers.d/kid-portal-health-check

install -m 644 deploy/xorg/99-kid-portal.conf /etc/X11/xorg.conf.d/99-kid-portal.conf
install -m 644 deploy/input/keyd-kid-portal.conf /etc/keyd/default.conf
if [[ -f deploy/alsa/asound.conf ]]; then
  install -m 644 deploy/alsa/asound.conf /etc/asound.conf
fi

install -m 644 deploy/security/fail2ban-sshd.local /etc/fail2ban/jail.d/kid-portal-sshd.local
install -d -m 755 /etc/ssh/sshd_config.d
install -m 644 deploy/security/sshd-hardening.conf /etc/ssh/sshd_config.d/99-kid-portal-hardening.conf
sshd -t

systemctl daemon-reload
systemctl restart systemd-journald || true
systemctl enable fail2ban keyd ssh
systemctl enable kid-portal.service kid-portal-admin.service kid-portal-network-access.path kid-portal-software-update.path kid-portal-wifi-watchdog.timer kid-portal-x.service kid-portal-kiosk.service
configure_zerotier

if [[ "$ALLOW_LAN_SSH" == "1" ]]; then
  ufw allow from "$LAN_CIDR" to any port 22 proto tcp
else
  ufw delete allow from "$LAN_CIDR" to any port 22 proto tcp >/dev/null 2>&1 || true
fi
ufw allow from "$LAN_CIDR" to any port 80 proto tcp
if [[ "$ENABLE_ZEROTIER" == "1" && -n "$ZEROTIER_INTERFACE" && -n "$MANAGEMENT_CIDR" ]]; then
  ufw allow in on "$ZEROTIER_INTERFACE" from "$MANAGEMENT_CIDR" to any port 22 proto tcp
  ufw allow in on "$ZEROTIER_INTERFACE" from "$MANAGEMENT_CIDR" to any port 80 proto tcp
elif [[ "$ENABLE_ZEROTIER" == "1" && -n "$ZEROTIER_NETWORK_ID" ]]; then
  echo "ZeroTier joined, but management firewall rules need both an assigned interface and KID_PORTAL_MANAGEMENT_CIDR." >&2
fi
ufw delete allow 8080/tcp >/dev/null 2>&1 || true
ufw delete allow from "$LAN_CIDR" to any port 8080 proto tcp >/dev/null 2>&1 || true
ufw --force enable

iw dev wlan0 set power_save off >/dev/null 2>&1 || true
ACTIVE_WIFI_CONNECTION="$(nmcli -t -f NAME,DEVICE connection show --active 2>/dev/null | awk -F: '$2 == "wlan0" {print $1; exit}')"
if [[ -n "$ACTIVE_WIFI_CONNECTION" ]]; then
  nmcli connection modify "$ACTIVE_WIFI_CONNECTION" 802-11-wireless.powersave 2 >/dev/null 2>&1 || true
fi

systemctl restart ssh fail2ban keyd kid-portal.service kid-portal-admin.service kid-portal-network-access.path kid-portal-software-update.path kid-portal-wifi-watchdog.timer
write_chromium_policy
systemctl restart kid-portal-x.service kid-portal-kiosk.service

echo "Kid Portal installed."
echo "Admin: http://$(hostname -I | awk '{print $1}')/"
