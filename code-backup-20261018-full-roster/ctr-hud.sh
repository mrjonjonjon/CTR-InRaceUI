#!/bin/bash
# Usage: ctr-hud.sh on|off|status   (double-click the Desktop shortcuts instead)
cd "$(dirname "$(readlink -f "$0")")" || exit 1
python3 ctr_hud.py "$@"
status=$?
if [ -t 1 ] && [ -n "$CTR_HUD_PAUSE" ]; then read -r -p "Press Enter to close..." _; fi
exit $status
