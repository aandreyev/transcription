#!/bin/bash
set -e
PLIST="$HOME/Library/LaunchAgents/com.transcription.app.plist"
launchctl unload "$PLIST" 2>/dev/null || true
rm -f "$PLIST"
echo "Removed LaunchAgent: $PLIST"

