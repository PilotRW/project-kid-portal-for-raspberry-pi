#!/usr/bin/env sh
set -eu

XRANDR_BIN="${XRANDR_BIN:-xrandr}"
URL="${KID_PORTAL_KIOSK_URL:-http://127.0.0.1:8080/}"

/usr/local/sbin/kid-portal-display-mode || true

GEOMETRY="$("$XRANDR_BIN" --query 2>/dev/null | awk '
  / connected/ {
    for (i = 1; i <= NF; i++) {
      if ($i ~ /^[0-9]+x[0-9]+\+[0-9]+\+[0-9]+/) {
        split($i, parts, /[x+]/)
        print parts[1] " " parts[2]
        exit
      }
    }
  }
')"

WIDTH="$(printf '%s\n' "$GEOMETRY" | awk '{print $1}')"
HEIGHT="$(printf '%s\n' "$GEOMETRY" | awk '{print $2}')"

WIDTH="${WIDTH:-1920}"
HEIGHT="${HEIGHT:-1080}"

exec /usr/bin/chromium \
  --user-data-dir=/home/pi/.config/kid-portal-chromium \
  --no-first-run \
  --no-default-browser-check \
  --disable-restore-session-state \
  --disable-extensions \
  --disable-component-extensions-with-background-pages \
  --disable-background-networking \
  --disable-sync \
  --enable-gpu-rasterization \
  --enable-zero-copy \
  --ignore-gpu-blocklist \
  --alsa-output-device=plughw:1,0 \
  --autoplay-policy=no-user-gesture-required \
  --kiosk \
  --start-fullscreen \
  --window-position=0,0 \
  --window-size="${WIDTH},${HEIGHT}" \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --disable-features=Translate,DesktopPWAsTabStrip,BackForwardCache \
  --overscroll-history-navigation=0 \
  "$URL"
