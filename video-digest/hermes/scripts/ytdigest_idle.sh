#!/bin/bash
# Hermes cron (no agent, every 30 min): process the YouTube backlog only when idle.
#   hermes cron create "every 30m" --name ytdigest-idle --script ytdigest_idle.sh --no-agent --deliver local
# Hermes kills cron scripts after 120 s, so the worker is started detached at the
# lowest CPU and IO priority; it checks the idle gate before every video and stops
# as soon as Filip becomes active or a budget is spent. Empty stdout = silent.
set -euo pipefail
REAL_HOME=$(getent passwd "$(id -un)" | cut -d: -f6)
YTD="$REAL_HOME/.hermes/ytdigest/venv/bin/ytdigest"
LOG="$REAL_HOME/.hermes/ytdigest/worker.log"
[ -x "$YTD" ] || { echo "ytdigest not installed at $YTD"; exit 0; }
set -a; [ -f "$REAL_HOME/.hermes/.env" ] && . "$REAL_HOME/.hermes/.env"; set +a
export HERMES_REAL_HOME="$REAL_HOME"
# Quick check first so a closed gate costs nothing and logs one line.
if ! "$YTD" gate >/dev/null 2>&1; then
  # Filip's own queued requests (priority 100) still run when the gate is closed
  setsid nohup "$YTD" worker --only-user --max-videos 3 --max-minutes 28 >>"$LOG" 2>&1 < /dev/null &
  exit 0
fi
setsid nohup nice -n 19 ionice -c3 "$YTD" worker --idle-only --max-videos 6 --max-minutes 28 >>"$LOG" 2>&1 < /dev/null &
exit 0
