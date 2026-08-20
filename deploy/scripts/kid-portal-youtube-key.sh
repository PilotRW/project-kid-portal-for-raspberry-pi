#!/bin/sh
set -eu

KEY_FILE="/etc/kid-portal/youtube-api-key.txt"
ACTION="${1:-}"

case "$ACTION" in
  set)
    tmp="$(mktemp)"
    clean="$(mktemp)"
    trap 'rm -f "$tmp" "$clean"' EXIT
    cat > "$tmp"
    tr -d '\r\n' < "$tmp" > "$clean"
    if [ ! -s "$clean" ]; then
      echo "API key is empty" >&2
      exit 2
    fi
    if grep -q '[[:space:]]' "$clean"; then
      echo "API key must not contain whitespace" >&2
      exit 2
    fi
    install -m 640 -o root -g pi "$clean" "$KEY_FILE"
    ;;
  clear)
    install -m 640 -o root -g pi /dev/null "$KEY_FILE"
    ;;
  *)
    echo "Usage: kid-portal-youtube-key {set|clear}" >&2
    exit 2
    ;;
esac
