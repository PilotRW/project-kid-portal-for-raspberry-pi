#!/bin/sh
set -eu

IFACE="${KID_PORTAL_WIFI_IFACE:-wlan0}"
ACTION="${1:-}"

case "$ACTION" in
  scan)
    exec nmcli -t --escape yes -f IN-USE,SSID,SIGNAL,SECURITY dev wifi list ifname "$IFACE" --rescan yes
    ;;
  status)
    exec nmcli -t --escape yes -f GENERAL.STATE,GENERAL.CONNECTION dev show "$IFACE"
    ;;
  connect)
    SSID="${2:-}"
    PASSWORD="${3:-}"
    if [ -z "$SSID" ]; then
      echo "SSID is required" >&2
      exit 2
    fi
    if [ -n "$PASSWORD" ]; then
      exec nmcli dev wifi connect "$SSID" password "$PASSWORD" ifname "$IFACE"
    fi
    exec nmcli dev wifi connect "$SSID" ifname "$IFACE"
    ;;
  *)
    echo "Usage: kid-portal-wifi {scan|status|connect SSID [PASSWORD]}" >&2
    exit 2
    ;;
esac
