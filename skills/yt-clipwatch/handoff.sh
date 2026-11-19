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
  # Hook files written by the poster: "<channel>_<clip>.hook.txt" = banner name / hook line / post id.
  # Re-render that clip with the hook; the loop above then sends <clip>_v2.mp4 back to Drive.
  for h in "$DEST"/*.hook.txt; do
    [ -f "$h" ] || continue
    base=$(basename "$h" .hook.txt)
    name=$(printf '%s' "$base" | grep -oE '[0-9]{8}-[0-9]{6}_x[0-9.]+$') || continue
    ch=${base%_"$name"}
    raw="clips/$ch/work/$name.mp4"
    [ -f "$raw" ] && [ ! -e "$raw.hookdone" ] || continue
    label=$(sed -n 1p "$h"); hook=$(sed -n 2p "$h")
    if python3 clipwatch.py --rerender "$raw" --name "$label" --hook "$hook" >/dev/null 2>&1; then
      rm -f "clips/$ch/${name}_v2.mp4.sent"  # a newer _v2 replaces an older one: send it again
      touch "$raw.hookdone"; echo "$(date +%H:%M:%S) re-rendered with hook: ${ch}_$name"
    else
      echo "$(date +%H:%M:%S) hook re-render failed: ${ch}_$name (will retry)"
    fi
  done
  sleep 60
done
