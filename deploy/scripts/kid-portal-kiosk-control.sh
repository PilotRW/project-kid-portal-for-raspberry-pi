#!/usr/bin/env sh
set -eu

case "${1:-}" in
  terminal)
    systemctl stop kid-portal-kiosk.service
    systemctl stop kid-portal-x.service
    systemctl unmask getty@tty1.service
    systemctl reset-failed getty@tty1.service
    systemctl start getty@tty1.service
    ;;
  kiosk)
    systemctl stop getty@tty1.service
    systemctl mask getty@tty1.service
    systemctl reset-failed getty@tty1.service kid-portal-x.service kid-portal-kiosk.service
    systemctl start kid-portal-x.service
    systemctl start kid-portal-kiosk.service
    ;;
  *)
    echo "Usage: kid-portal-kiosk-control terminal|kiosk" >&2
    exit 2
    ;;
esac
