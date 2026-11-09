#!/bin/bash
cd "$(dirname "$0")"
bash scripts/install-skill.sh
printf '\nPress Enter to close.'; read -r _
