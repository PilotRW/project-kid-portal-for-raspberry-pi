#!/bin/sh
set -eu

LOG_FILE="/var/log/kid-portal-software-update.log"
LOCK_FILE="/run/kid-portal-software-update.lock"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "$(date -Is) Kid Portal software update is already running." >> "$LOG_FILE"
  exit 75
fi

export DEBIAN_FRONTEND=noninteractive

{
  echo "== Kid Portal software update started: $(date -Is) =="
  apt-get update
  apt-get -y \
    -o Dpkg::Options::=--force-confdef \
    -o Dpkg::Options::=--force-confold \
    full-upgrade
  apt-get -y autoremove
  echo "== Kid Portal software update finished: $(date -Is) =="
} >> "$LOG_FILE" 2>&1
