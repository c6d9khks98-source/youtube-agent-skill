#!/bin/bash
# run-all.sh - start every clipper plus the Google Drive hand-off in the background, once.
#   bash run-all.sh        start whatever is not running yet (safe to run again any time)
#   bash run-all.sh stop   stop everything
#   bash status.sh         see what runs and what it has done
# Everything keeps running after the Terminal window is closed (nohup). The Mac must stay awake:
# each process holds a caffeinate wake lock while it runs.
cd "$(dirname "$0")" || exit 1
export PATH="/opt/homebrew/opt/ffmpeg-full/bin:$PATH"
mkdir -p logs

# channel  settings   (edit here to add or drop a streamer, then: bash run-all.sh)
CHANNELS=(
  "yourragegaming --min-msgs 25 --k 3.5"
  "brucedropemoff --min-msgs 18 --k 3"
  "ishowspeed --min-msgs 60 --k 3"
)

if [ "$1" = "stop" ]; then
  # TERM, not INT: background jobs ignore Ctrl-C's signal. clipwatch.py treats TERM as a clean stop.
  pkill -TERM -f "clipwatch.py" ; pkill -TERM -f "bash handoff.sh"
  sleep 15; pgrep -f "clipwatch.py|handoff.sh" >/dev/null && echo "still stopping, check again in a minute" || echo "all stopped"
  exit 0
fi

for line in "${CHANNELS[@]}"; do
  set -- $line; name=$1; shift
  if pgrep -f "clipwatch.py $name" >/dev/null; then
    echo "already running: $name"
  else
    nohup caffeinate -i python3 clipwatch.py "$name" "$@" --verbose > "logs/$name.log" 2>&1 &
    echo "started:         $name"
  fi
done
if pgrep -f "bash handoff.sh" >/dev/null; then
  echo "already running: hand-off to Google Drive"
else
  nohup caffeinate -i bash handoff.sh > logs/handoff.log 2>&1 &
  echo "started:         hand-off to Google Drive"
fi
echo "done - you can close this window. Check any time with: bash status.sh"
