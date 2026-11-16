#!/usr/bin/env bash
# Hermes no-agent cron wrapper: break reminder after long Steam sessions (empty stdout = silent).
#   hermes cron create "every 10m" --name steam-break --script steam_break.sh --no-agent --deliver matrix
set -euo pipefail
home="$(getent passwd "$(id -un)" | cut -d: -f6)"
exec python3 "$home/.hermes/scripts/steam-games/steam_games.py" przerwa --cron
