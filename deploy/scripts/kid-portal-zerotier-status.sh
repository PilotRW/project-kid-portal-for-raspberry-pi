#!/usr/bin/env sh
set -eu

CACHE_PATH="/run/kid-portal-zerotier-status.json"

render_status() {
  printf '{"info":'
  /usr/sbin/zerotier-cli -j info
  printf ',"networks":'
  /usr/sbin/zerotier-cli -j listnetworks
  printf '}\n'
}

if [ "$#" -eq 0 ]; then
  render_status
  exit 0
fi

if [ "$#" -ne 1 ] || [ "$1" != "--write-cache" ]; then
  echo "Usage: kid-portal-zerotier-status [--write-cache]" >&2
  exit 2
fi

tmp_file="$(mktemp "${CACHE_PATH}.XXXXXX")"
trap 'rm -f "$tmp_file"' EXIT
render_status > "$tmp_file"
chmod 644 "$tmp_file"
mv -f "$tmp_file" "$CACHE_PATH"
trap - EXIT
