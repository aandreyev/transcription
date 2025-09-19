#!/bin/bash
set -e
APP_DIR="$HOME/Applications/Transcription"
PLIST="$HOME/Library/LaunchAgents/com.transcription.app.plist"

mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.transcription.app</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-lc</string>
    <string>cd "$APP_DIR" && ./run.sh</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$APP_DIR/logs/launchagent.out.log</string>
  <key>StandardErrorPath</key>
  <string>$APP_DIR/logs/launchagent.err.log</string>
</dict>
</plist>
EOF

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "Installed and loaded LaunchAgent: $PLIST"

