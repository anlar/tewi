#! /usr/bin/env sh

MAGNET='magnet:?xt=urn:btih:d4487f489d4ee786f99bcdeeb8d3f226694ea27f&dn=archlinux-2025.11.01-x86_64.iso'

transmission-remote localhost:9092 --add "$MAGNET"

