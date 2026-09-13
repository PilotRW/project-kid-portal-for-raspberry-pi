#!/bin/sh
set -eu

CONFIG_PATH="${KID_PORTAL_CONFIG:-/etc/kid-portal/config.json}"
MODE="${1:-}"
XRANDR_BIN="${XRANDR_BIN:-xrandr}"

if [ -z "$MODE" ] && [ -r "$CONFIG_PATH" ]; then
  MODE="$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1])).get("display", {}).get("mode", "1080p"))' "$CONFIG_PATH" 2>/dev/null || echo 1080p)"
fi
MODE="${MODE:-1080p}"

case "$MODE" in
  4k)
    XRANDR_MODE="3840x2160"
    ;;
  1080p)
    XRANDR_MODE="1920x1080"
    ;;
  *)
    echo "Unsupported display mode: $MODE" >&2
    exit 2
    ;;
esac

OUTPUT=""
i=0
while [ "$i" -lt 30 ]; do
  OUTPUT="$("$XRANDR_BIN" --query 2>/dev/null | awk '/ connected/{print $1; exit}')"
  if [ -n "$OUTPUT" ]; then
    break
  fi
  i=$((i + 1))
  sleep 1
done

[ -n "$OUTPUT" ] || exit 0

"$XRANDR_BIN" --output "$OUTPUT" --mode "$XRANDR_MODE" --rate 60 || true
xset s off -dpms s noblank || true
