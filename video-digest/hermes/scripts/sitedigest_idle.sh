#!/bin/bash
export PATH="$HOME/.local/bin:$HOME/.deno/bin:$PATH"  # deno for yt-dlp
# Hermes cron (no agent, at :15 and :45, between the YouTube worker runs): digest
# lessons of mapped course sites only while Hermes is idle. Same idle gate as the
# YouTube backlog (Filip quiet, no tasks of his, budget left, machine not busy);
# re-checked before every lesson. Mapping a site and Filip's own `sitedigest digest`
# runs are started by hand or by the course-digest skill, not here.
#   hermes cron create "15,45 * * * *" --name sitedigest-idle --script sitedigest_idle.sh --no-agent --deliver local
set -euo pipefail
REAL_HOME=$(getent passwd "$(id -un)" | cut -d: -f6)
SD="$REAL_HOME/.hermes/ytdigest/venv/bin/sitedigest"
YTD="$REAL_HOME/.hermes/ytdigest/venv/bin/ytdigest"
LOG="$REAL_HOME/.hermes/sitedigest/worker.log"
[ -x "$SD" ] || exit 0
ls "$REAL_HOME"/.hermes/sitedigest/*/map.json >/dev/null 2>&1 || exit 0   # no site mapped yet
set -a; [ -f "$REAL_HOME/.hermes/.env" ] && . "$REAL_HOME/.hermes/.env"; set +a
export HERMES_REAL_HOME="$REAL_HOME"
"$YTD" gate >/dev/null 2>&1 || exit 0
setsid nohup nice -n 19 ionice -c3 "$SD" worker --idle-only --max-pages 4 --max-minutes 28 >>"$LOG" 2>&1 < /dev/null &
exit 0
