#! /usr/bin/env sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cat "$SCRIPT_DIR/magnets.txt" | xargs -L 1 transmission-remote localhost:9092 --add

transmission-remote localhost:9092 -l | awk 'NR>1 && !/^Sum:/ {print $1}' | while read id; do 
  rand=$(od -An -N1 -tu1 /dev/urandom | awk '{print $1 % 3}')
  case $rand in
    0) transmission-remote localhost:9092 -t "$id" -Bh ;;
    1) transmission-remote localhost:9092 -t "$id" -Bl ;;
    2) transmission-remote localhost:9092 -t "$id" -Bn ;;
  esac
done
