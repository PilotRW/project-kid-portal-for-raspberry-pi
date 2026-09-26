#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-}"
USER="${2:-pi}"
REMOTE_DIR="${KID_PORTAL_REMOTE_DIR:-/tmp/kid-portal-bootstrap}"
LAN_CIDR="${KID_PORTAL_LAN_CIDR:-192.168.0.0/24}"
MANAGEMENT_CIDR="${KID_PORTAL_MANAGEMENT_CIDR:-}"
ALLOW_LAN_SSH="${KID_PORTAL_ALLOW_LAN_SSH:-1}"
ENABLE_ZEROTIER="${KID_PORTAL_ENABLE_ZEROTIER:-0}"
ZEROTIER_NETWORK_ID="${KID_PORTAL_ZEROTIER_NETWORK_ID:-}"

if [[ -z "$HOST" ]]; then
  echo "Usage: $0 <pi-host-or-ip> [ssh-user]" >&2
  echo "Example: $0 192.168.0.142 pi" >&2
  exit 2
fi

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

rsync -az --delete \
  --exclude ".git/" \
  --exclude ".pytest_cache/" \
  --exclude ".venv/" \
  --exclude "__pycache__/" \
  "$PROJECT_DIR/" "$USER@$HOST:$REMOTE_DIR/"

ssh -t "$USER@$HOST" "KID_PORTAL_LAN_CIDR='$LAN_CIDR' KID_PORTAL_MANAGEMENT_CIDR='$MANAGEMENT_CIDR' KID_PORTAL_ALLOW_LAN_SSH='$ALLOW_LAN_SSH' KID_PORTAL_ENABLE_ZEROTIER='$ENABLE_ZEROTIER' KID_PORTAL_ZEROTIER_NETWORK_ID='$ZEROTIER_NETWORK_ID' sudo -E bash '$REMOTE_DIR/deploy/scripts/pi-install.sh' '$REMOTE_DIR'"
ssh -t "$USER@$HOST" "sudo reboot" || true

echo "Bootstrap complete. The Pi is rebooting."
echo "After it returns: ./deploy/check-pi.sh $HOST $USER"
