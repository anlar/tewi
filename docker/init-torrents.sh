#! /usr/bin/env sh

LIMIT=${1:-2}

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Transmission

head -n $LIMIT "$SCRIPT_DIR/magnets.txt" | xargs -L 1 transmission-remote localhost:9070 --add

transmission-remote localhost:9070 -l | awk 'NR>1 && !/^Sum:/ {print $1}' | while read id; do 
  rand=$(od -An -N1 -tu1 /dev/urandom | awk '{print $1 % 3}')
  case $rand in
    0) transmission-remote localhost:9070 -t "$id" -Bh ;;
    1) transmission-remote localhost:9070 -t "$id" -Bl ;;
    2) transmission-remote localhost:9070 -t "$id" -Bn ;;
  esac
done

# qBittorrent

qbt_password=$(docker logs tewi-qbittorrent-dev 2>&1 | grep 'temporary password' | tail -1 | sed 's/.*: //')

echo "qbt password: $qbt_password"

qbt_session=$(curl -i --header 'Referer: http://localhost:9071' --data "username=admin&password=$qbt_password" http://localhost:9071/api/v2/auth/login | grep set-cookie | cut -d';' -f1 | cut -d'=' -f2)

echo "qbt session: $qbt_session"

head -n $LIMIT "$SCRIPT_DIR/magnets.txt" | xargs -I {} curl -X POST -H "Referer: http://localhost:9071" -b "SID=$qbt_session" --data-urlencode "urls={}" http://localhost:9071/api/v2/torrents/add

# Deluge

deluge_session=$(curl -i -X POST http://localhost:9072/json -H "Content-Type: application/json" -d '{"method": "auth.login","params": ["deluge"],"id": 1}' | grep Set-Cookie | cut -d';' -f1 | cut -d'=' -f2)

echo "deluge session: $deluge_session"

deluge_host=$(curl -X POST http://localhost:9072/json -H "Content-Type: application/json" -d '{"method": "web.get_hosts", "params": [], "id": 2}' --cookie "_session_id=$deluge_session" | jq -r '.result[0][0]')

echo "deluge host: $deluge_host"

curl -X POST http://localhost:9072/json -H "Content-Type: application/json" -d '{"method": "web.connect", "params": ["'$deluge_host'"], "id": 3}' --cookie "_session_id=$deluge_session"

head -n $LIMIT "$SCRIPT_DIR/magnets.txt" | xargs -I }{ curl -X POST http://localhost:9072/json -H "Content-Type: application/json" -d '{"method": "core.add_torrent_magnet","params": ["}{", {}],"id": 1}' --cookie "_session_id=$deluge_session"

