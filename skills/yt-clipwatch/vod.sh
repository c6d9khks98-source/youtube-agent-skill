#!/bin/bash
# vod.sh - clip a FINISHED stream (one the live clipper missed) into the same pipeline.
#   bash vod.sh https://www.twitch.tv/videos/1234567890 ishowspeed
#   bash vod.sh https://www.twitch.tv/videos/1234567890 ishowspeed --vod-from 01:00:00 --vod-length 02:00:00
# The clips land in clips/<channel>/ like live clips; handoff.sh sends them to Drive and the
# hourly poster picks the best ones, with masked captions and the handle titles. Nothing else to do.
cd "$(dirname "$0")" || exit 1
export PATH="/opt/homebrew/opt/ffmpeg-full/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
[ -n "$2" ] || { echo "usage: bash vod.sh <twitch VOD link> <channel> [options]"; exit 1; }
url="$1"; ch="$2"; shift 2
exec python3 clipwatch.py --vod "$url" "$ch" "$@"
