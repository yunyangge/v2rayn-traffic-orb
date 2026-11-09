#!/bin/bash
set -euo pipefail
PACKAGE="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE="$PACKAGE/TrafficOrb.app"
TARGET="${TRAFFIC_ORB_INSTALL_DIR:-$HOME/Applications}/TrafficOrb.app"
LABEL=app.trafficorb.lifecycle
AGENT="${TRAFFIC_ORB_AGENT_DIR:-$HOME/Library/LaunchAgents}/$LABEL.plist"
if [[ "$(uname -s)" != Darwin || ! -d "$SOURCE" ]]; then echo 'Please use a macOS release package.'; exit 1; fi
BUILT="$(cat "$SOURCE/Contents/Resources/architecture.txt")"
if [[ "$BUILT" != "$(uname -m)" ]]; then echo "Wrong architecture: package=$BUILT, Mac=$(uname -m)."; exit 1; fi
if [[ "${1:-}" == --dry-run ]]; then printf 'Would install app and lifecycle agent; existing data is preserved.\n'; exit 0; fi
mkdir -p "$(dirname "$TARGET")" "$(dirname "$AGENT")"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
if [[ -x "$TARGET/Contents/MacOS/LifecycleWatcher" ]]; then "$TARGET/Contents/MacOS/LifecycleWatcher" --stop-companions; fi
if [[ -e "$TARGET.previous" ]]; then echo "Remove or move the previous upgrade backup: $TARGET.previous"; exit 1; fi
if [[ -d "$TARGET" ]]; then mv "$TARGET" "$TARGET.previous"; fi
ditto "$SOURCE" "$TARGET"
# PlistBuddy writes path strings correctly, including spaces and XML characters.
TMP="$AGENT.tmp"
printf '%s\n' '<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd"><plist version="1.0"><dict/></plist>' > "$TMP"
PB=/usr/libexec/PlistBuddy
"$PB" -c "Add :Label string $LABEL" "$TMP"
"$PB" -c 'Add :ProgramArguments array' "$TMP"
"$PB" -c "Add :ProgramArguments:0 string $TARGET/Contents/MacOS/LifecycleWatcher" "$TMP"
"$PB" -c 'Add :RunAtLoad bool true' "$TMP"
"$PB" -c 'Add :KeepAlive bool true' "$TMP"
"$PB" -c 'Add :LimitLoadToSessionType string Aqua' "$TMP"
"$PB" -c 'Add :ThrottleInterval integer 10' "$TMP"
"$PB" -c 'Add :ProcessType string Background' "$TMP"
mv "$TMP" "$AGENT"
launchctl bootstrap "gui/$(id -u)" "$AGENT"
echo 'Installed. Open v2rayN to show the orb; quitting v2rayN stops the orb and collector.'
echo 'If waiting for statistics, enable traffic statistics in v2rayN settings and restart its service.'
echo 'App: ~/Applications/TrafficOrb.app. No administrator password is needed.'
