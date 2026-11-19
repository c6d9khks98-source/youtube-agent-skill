#!/bin/bash
# status.sh - what is running, and the latest from each clipper.
cd "$(dirname "$0")" || exit 1
echo "== running"
R=$(ps -axo command | grep -v -e grep -e caffeinate | grep -o "clipwatch.py [a-z_0-9]*\|bash handoff.sh" | sort -u)
echo "${R:-(nothing - start with: bash run-all.sh)}"
for f in logs/*.log *.log; do
  [ -f "$f" ] || continue
  case "$f" in logs/handoff.log) echo "== hand-off"; tail -2 "$f"; continue;; esac
  echo "== $f"
  grep -hE "REC|CLIP|CUT|SEND" "$f" | tail -3
done
