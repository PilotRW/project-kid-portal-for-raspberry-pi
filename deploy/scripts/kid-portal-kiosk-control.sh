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
  restart-kiosk)
    systemctl reset-failed kid-portal-x.service kid-portal-kiosk.service
    systemctl stop kid-portal-kiosk.service
    systemctl restart kid-portal-x.service
    i=0
    while [ "$i" -lt 20 ]; do
      systemctl is-active --quiet kid-portal-x.service && break
      i=$((i + 1))
      sleep 1
    done
    systemctl start kid-portal-kiosk.service
    ;;
  reboot)
    systemctl reboot
    ;;
  *)
    echo "Usage: kid-portal-kiosk-control terminal|kiosk|restart-kiosk|reboot" >&2
    exit 2
    ;;
esac
