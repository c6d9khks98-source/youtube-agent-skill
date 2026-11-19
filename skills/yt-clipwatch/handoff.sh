#!/bin/bash
# handoff.sh - copy every finished clip (once) into the Google Drive for desktop folder
# "clips-approved", where the scheduled poster picks it up and schedules it on Metricool.
#
#   bash handoff.sh                 # finds ~/Library/CloudStorage/GoogleDrive-*/My Drive/clips-approved
#   bash handoff.sh /some/folder    # or hand off to any folder you name
#
# Runs next to clipwatch.py; the clippers themselves do not need a restart. A clip is sent once
# it has not changed for a minute (so never half-written); a <clip>.mp4.sent marker stops a
# second copy. Ctrl-C stops it.
DEST="${1:-$(ls -d "$HOME"/Library/CloudStorage/GoogleDrive-*/"My Drive"/clips-approved 2>/dev/null | head -1)}"
if [ ! -d "$DEST" ]; then
  echo "No 'clips-approved' folder found in Google Drive for desktop."
  echo "Install Google Drive for desktop, sign in with the account that owns the folder, wait until"
  echo "'My Drive' shows in Finder, then run this again."
  exit 1
fi
cd "$(dirname "$0")" || exit 1
echo "$(date +%H:%M:%S) handing finished clips to: $DEST"
while true; do
  find clips -mindepth 2 -maxdepth 2 -name '20*.mp4' -mmin +1 ! -path 'clips/simulated/*' 2>/dev/null |
  while IFS= read -r f; do
    [ -e "$f.sent" ] && continue
    c=$(basename "$(dirname "$f")"); b=$(basename "$f" .mp4)
    for s in "clips/$c/work/$b.srt" "clips/$c/$b.srt"; do
      if [ -f "$s" ]; then cp "$s" "$DEST/${c}_$b.srt"; break; fi
    done
    if cp "$f" "$DEST/${c}_$b.mp4.part" && mv "$DEST/${c}_$b.mp4.part" "$DEST/${c}_$b.mp4"; then
      touch "$f.sent"
      echo "$(date +%H:%M:%S) sent ${c}_$b.mp4"
    else
      echo "$(date +%H:%M:%S) could not copy $f (will retry)"
    fi
  done
  sleep 60
done
