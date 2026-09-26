#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-}"
USER="${2:-pi}"
ADMIN_PIN="${KID_PORTAL_ADMIN_PIN:-1234}"

if [[ -z "$HOST" ]]; then
  echo "Usage: $0 <pi-host-or-ip> [ssh-user]" >&2
  exit 2
fi

ssh "$USER@$HOST" "KID_PORTAL_ADMIN_PIN='$ADMIN_PIN' bash -s" <<'REMOTE_CHECK'
set -e
echo "== Host =="
hostname
ip -4 -brief addr
echo
echo "== Services =="
systemctl is-active ssh fail2ban kid-portal.service kid-portal-admin.service kid-portal-network-access.path kid-portal-software-update.path kid-portal-wifi-watchdog.timer kid-portal-x.service kid-portal-kiosk.service
echo
echo "== UFW =="
sudo -n /usr/sbin/ufw status
echo
echo "== Network =="
if [[ -x /usr/sbin/iw ]]; then
  /usr/sbin/iw dev wlan0 get power_save || true
else
  echo "iw: not installed"
fi
ACTIVE_WIFI_CONNECTION="$(nmcli -t -f NAME,DEVICE connection show --active 2>/dev/null | awk -F: '$2 == "wlan0" {print $1; exit}')"
if [[ -n "$ACTIVE_WIFI_CONNECTION" ]]; then
  printf "active_connection=%s\n" "$ACTIVE_WIFI_CONNECTION"
  printf "wifi_powersave=%s\n" "$(nmcli -g 802-11-wireless.powersave connection show "$ACTIVE_WIFI_CONNECTION" 2>/dev/null || true)"
fi
systemctl list-timers kid-portal-wifi-watchdog.timer --no-pager || true
echo
echo "== ZeroTier =="
if systemctl list-unit-files zerotier-one.service --no-legend 2>/dev/null | grep -q '^zerotier-one.service'; then
  systemctl is-active zerotier-one.service
  sudo -n /usr/local/sbin/kid-portal-zerotier-status
else
  echo "not installed"
fi
echo
echo "== Journal =="
journalctl --list-boots --no-pager | tail -n 5
echo
echo "== fail2ban =="
sudo -n /usr/bin/fail2ban-client status sshd
echo
echo "== HTTP =="
curl -fsS http://127.0.0.1:8080/api/youtube/status
echo
curl -fsS -X POST http://127.0.0.1/api/admin/state -H "Content-Type: application/json" -d "{\"pin\":\"${KID_PORTAL_ADMIN_PIN}\"}" | python3 -m json.tool | sed -n "1,80p"
echo
echo "== Display =="
DISPLAY=:0 xrandr --query | sed -n "1,6p" || true
REMOTE_CHECK
