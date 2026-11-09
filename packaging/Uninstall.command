#!/bin/bash
cd "$(dirname "$0")"
bash scripts/uninstall.sh
printf '\nPress Enter to close.'; read -r _
