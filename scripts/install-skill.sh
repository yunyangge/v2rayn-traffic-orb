#!/bin/bash
set -euo pipefail
PACKAGE="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${CODEX_HOME:-$HOME/.codex}/skills/traffic-orb"
if [[ -d "$DEST" ]]; then
  echo "Skill already exists at $DEST. It was not overwritten."
  exit 1
fi
mkdir -p "$(dirname "$DEST")"
ditto "$PACKAGE/skills/traffic-orb" "$DEST"
echo 'Installed $traffic-orb. Restart Codex or start a new chat to load it.'
