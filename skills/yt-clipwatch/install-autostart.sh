#!/bin/bash
# install-autostart.sh - make the Mac restart the clippers by itself (macOS only).
#   bash install-autostart.sh          install: runs run-all.sh at login and every 5 minutes
#   bash install-autostart.sh remove   uninstall
# run-all.sh only starts what is not already running, so running it every 5 minutes simply brings
# back anything that stopped: after the lid was closed, a restart, a crash.
DIR="$(cd "$(dirname "$0")" && pwd)"
LABEL="com.gtaspikeclips.runall"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

launchctl unload "$PLIST" 2>/dev/null
if [ "$1" = "remove" ]; then
  rm -f "$PLIST"; echo "autostart removed (running clippers keep running until: bash run-all.sh stop)"; exit 0
fi

mkdir -p "$HOME/Library/LaunchAgents" "$DIR/logs"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>$DIR/run-all.sh</string></array>
  <key>RunAtLoad</key><true/>
  <key>StartInterval</key><integer>300</integer>
  <key>AbandonProcessGroup</key><true/>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>/opt/homebrew/opt/ffmpeg-full/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
  <key>StandardOutPath</key><string>$DIR/logs/autostart.log</string>
  <key>StandardErrorPath</key><string>$DIR/logs/autostart.log</string>
</dict>
</plist>
EOF
launchctl load -w "$PLIST" && echo "autostart installed: the clippers come back by themselves within 5 minutes of the Mac waking up or logging in."
