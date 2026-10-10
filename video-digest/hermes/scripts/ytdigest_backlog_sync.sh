#!/bin/bash
export PATH="$HOME/.local/bin:$HOME/.deno/bin:$PATH"  # deno for yt-dlp
# Hermes cron (no agent, daily 04:30): queue new videos from every account's playlists
# and Watch Later. Costs no model tokens (YouTube API + yt-dlp metadata only).
#   hermes cron create "30 4 * * *" --name ytdigest-backlog-sync --script ytdigest_backlog_sync.sh --no-agent --deliver local
set -euo pipefail
REAL_HOME=$(getent passwd "$(id -un)" | cut -d: -f6)
YTD="$REAL_HOME/.hermes/ytdigest/venv/bin/ytdigest"
[ -x "$YTD" ] || { echo "ytdigest not installed at $YTD"; exit 0; }
set -a; [ -f "$REAL_HOME/.hermes/.env" ] && . "$REAL_HOME/.hermes/.env"; set +a
export HERMES_REAL_HOME="$REAL_HOME"
setsid nohup nice -n 19 "$YTD" backlog-sync >>"$REAL_HOME/.hermes/ytdigest/backlog-sync.log" 2>&1 < /dev/null &
exit 0
