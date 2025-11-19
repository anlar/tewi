#! /usr/bin/env sh

LIMIT=${1:-2}

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Transmission

head -n $LIMIT "$SCRIPT_DIR/magnets.txt" | xargs -L 1 transmission-remote localhost:9092 --add

transmission-remote localhost:9092 -l | awk 'NR>1 && !/^Sum:/ {print $1}' | while read id; do 
  rand=$(od -An -N1 -tu1 /dev/urandom | awk '{print $1 % 3}')
  case $rand in
    0) transmission-remote localhost:9092 -t "$id" -Bh ;;
    1) transmission-remote localhost:9092 -t "$id" -Bl ;;
    2) transmission-remote localhost:9092 -t "$id" -Bn ;;
  esac
done

# qBittorrent

qbt_password=$(docker logs tewi-qbittorrent-dev 2>&1 | grep 'temporary password' | tail -1 | sed 's/.*: //')

echo "qbt password: $qbt_password"

qbt_session=$(curl -i --header 'Referer: http://localhost:9093' --data "username=admin&password=$qbt_password" http://localhost:9093/api/v2/auth/login | grep set-cookie | cut -d';' -f1 | cut -d'=' -f2)

echo "qbt session: $qbt_session"

head -n $LIMIT "$SCRIPT_DIR/magnets.txt" | xargs -I {} curl -X POST -H "Referer: http://localhost:9093" -b "SID=$qbt_session" --data-urlencode "urls={}" http://localhost:9093/api/v2/torrents/add

