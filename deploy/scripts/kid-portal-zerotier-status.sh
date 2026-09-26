#!/usr/bin/env sh
set -eu

if [ "$#" -ne 0 ]; then
  echo "Usage: kid-portal-zerotier-status" >&2
  exit 2
fi

printf '{"info":'
/usr/sbin/zerotier-cli -j info
printf ',"networks":'
/usr/sbin/zerotier-cli -j listnetworks
printf '}\n'
