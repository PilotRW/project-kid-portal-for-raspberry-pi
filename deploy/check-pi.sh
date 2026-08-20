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
systemctl is-active ssh fail2ban kid-portal.service kid-portal-admin.service kid-portal-network-access.path kid-portal-x.service kid-portal-kiosk.service
echo
echo "== UFW =="
sudo ufw status
echo
echo "== fail2ban =="
sudo fail2ban-client status sshd
echo
echo "== HTTP =="
curl -fsS http://127.0.0.1:8080/api/youtube/status
echo
curl -fsS -X POST http://127.0.0.1/api/admin/state -H "Content-Type: application/json" -d "{\"pin\":\"${KID_PORTAL_ADMIN_PIN}\"}" | python3 -m json.tool | sed -n "1,80p"
echo
echo "== Display =="
DISPLAY=:0 xrandr --query | sed -n "1,6p" || true
REMOTE_CHECK
