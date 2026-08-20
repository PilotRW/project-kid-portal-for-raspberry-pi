#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-}"
USER="${2:-pi}"
REMOTE_DIR="${KID_PORTAL_REMOTE_DIR:-/tmp/kid-portal-deploy}"
LAN_CIDR="${KID_PORTAL_LAN_CIDR:-192.168.0.0/24}"

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

ssh "$USER@$HOST" "KID_PORTAL_SKIP_APT=1 KID_PORTAL_LAN_CIDR='$LAN_CIDR' sudo -E bash '$REMOTE_DIR/deploy/scripts/pi-install.sh' '$REMOTE_DIR'"
./deploy/check-pi.sh "$HOST" "$USER"
