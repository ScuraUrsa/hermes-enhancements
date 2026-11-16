#!/usr/bin/env bash
# Hermes no-agent cron wrapper: new Steam achievements -> XP in ~/.hermes/autonomy/steam-games/xp.jsonl.
# Prints only when something new was unlocked (empty stdout = silent).
#   hermes cron create "0 21 * * *" --name steam-achievements --script steam_achievements.sh --no-agent --deliver matrix
set -euo pipefail
home="$(getent passwd "$(id -un)" | cut -d: -f6)"
exec python3 "$home/.hermes/scripts/steam-games/steam_games.py" osiagniecia --cron
