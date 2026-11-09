#!/bin/bash
set -euo pipefail
TARGET="${TRAFFIC_ORB_INSTALL_DIR:-$HOME/Applications}/TrafficOrb.app"
AGENT="${TRAFFIC_ORB_AGENT_DIR:-$HOME/Library/LaunchAgents}/app.trafficorb.lifecycle.plist"
launchctl bootout "gui/$(id -u)/app.trafficorb.lifecycle" 2>/dev/null || true
if [[ -x "$TARGET/Contents/MacOS/LifecycleWatcher" ]]; then "$TARGET/Contents/MacOS/LifecycleWatcher" --stop-companions; fi
if [[ -f "$AGENT" ]]; then rm "$AGENT"; fi
# Move the app to Trash; do not delete settings or traffic history.
if [[ -d "$TARGET" ]]; then mv "$TARGET" "$HOME/.Trash/TrafficOrb-$(date +%Y%m%d-%H%M%S).app"; fi
echo 'Uninstalled. Settings/history remain in ~/Library/Application Support/TrafficOrb.'
