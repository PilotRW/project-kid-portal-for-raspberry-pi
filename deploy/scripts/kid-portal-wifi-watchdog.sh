#!/usr/bin/env bash
set -euo pipefail

LOG_TAG="kid-portal-wifi-watchdog"
PING_COUNT="${KID_PORTAL_WIFI_WATCHDOG_PING_COUNT:-2}"
PING_TIMEOUT="${KID_PORTAL_WIFI_WATCHDOG_PING_TIMEOUT:-2}"
RECOVERY_WAIT="${KID_PORTAL_WIFI_WATCHDOG_RECOVERY_WAIT:-8}"

log() {
  logger -t "$LOG_TAG" "$*"
  echo "$LOG_TAG: $*"
}

gateway() {
  ip route show default 2>/dev/null | awk '$5 == "wlan0" {print $3; exit} $1 == "default" {print $3; exit}'
}

active_wifi_connection() {
  nmcli -t -f NAME,DEVICE connection show --active 2>/dev/null | awk -F: '$2 == "wlan0" {print $1; exit}'
}

saved_wifi_connection() {
  nmcli -t -f NAME,TYPE,AUTOCONNECT connection show 2>/dev/null | awk -F: '$2 == "802-11-wireless" && $3 == "yes" {print $1; exit}'
}

ping_gateway() {
  local gw="$1"
  [[ -n "$gw" ]] && ping -I wlan0 -c "$PING_COUNT" -W "$PING_TIMEOUT" "$gw" >/dev/null 2>&1
}

GW="$(gateway)"
if ping_gateway "$GW"; then
  exit 0
fi

CONNECTION="$(active_wifi_connection)"
if [[ -z "$CONNECTION" ]]; then
  CONNECTION="$(saved_wifi_connection)"
fi

log "Wi-Fi gateway check failed${GW:+ for $GW}; attempting recovery${CONNECTION:+ via $CONNECTION}"

nmcli radio wifi on >/dev/null 2>&1 || true
if [[ -n "$CONNECTION" ]]; then
  nmcli connection up "$CONNECTION" >/dev/null 2>&1 || true
fi

sleep "$RECOVERY_WAIT"
GW="$(gateway)"
if ping_gateway "$GW"; then
  log "Wi-Fi recovered after reconnect${GW:+ via $GW}"
  exit 0
fi

log "Wi-Fi reconnect did not recover LAN; restarting NetworkManager"
systemctl restart NetworkManager.service

sleep "$RECOVERY_WAIT"
GW="$(gateway)"
if ping_gateway "$GW"; then
  log "Wi-Fi recovered after NetworkManager restart${GW:+ via $GW}"
  exit 0
fi

log "Wi-Fi still unreachable after recovery attempts"
exit 1
