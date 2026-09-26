#!/usr/bin/env sh
set -eu

if [ "$#" -ne 0 ]; then
  echo "Usage: kid-portal-zerotier-status" >&2
  exit 2
fi

/usr/sbin/zerotier-cli info
/usr/sbin/zerotier-cli listnetworks
