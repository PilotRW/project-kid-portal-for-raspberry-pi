#!/bin/sh
set -eu

CONFIG_PATH="${KID_PORTAL_CONFIG:-/etc/kid-portal/config.json}"
MODE="${1:-}"

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

OUTPUT="$(xrandr --query | awk '/ connected/{print $1; exit}')"
if [ -z "$OUTPUT" ]; then
  exit 0
fi

xrandr --output "$OUTPUT" --mode "$XRANDR_MODE" --rate 60 || true
xset s off -dpms s noblank || true
