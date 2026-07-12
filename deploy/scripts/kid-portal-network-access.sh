#!/bin/sh
set -eu

REQUEST_FILE="/run/kid-portal/network-access.request"
STATE_FILE="/run/kid-portal/network-access.state"
LAN_CIDR="192.168.0.0/24"

mkdir -p /run/kid-portal

if [ ! -f "$REQUEST_FILE" ]; then
  exit 0
fi

REQUEST="$(tr -d '\r\n ' < "$REQUEST_FILE")"

case "$REQUEST" in
  enabled)
    ufw allow from "$LAN_CIDR" to any port 8080 proto tcp >/dev/null
    printf "enabled\n" > "$STATE_FILE"
    ;;
  disabled)
    ufw delete allow from "$LAN_CIDR" to any port 8080 proto tcp >/dev/null 2>&1 || true
    ufw delete allow 8080/tcp >/dev/null 2>&1 || true
    printf "disabled\n" > "$STATE_FILE"
    ;;
  *)
    printf "disabled\n" > "$STATE_FILE"
    exit 1
    ;;
esac
