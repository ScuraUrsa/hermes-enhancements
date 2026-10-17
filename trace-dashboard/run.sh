#!/bin/bash
# One collector run on prod: gather the inputs, build trace.json, publish the page.
# Started by trace-dashboard-collect.timer (WOBI role trace_dashboard). Safe to run by hand.
# Secrets: the GitHub token is read from Bitwarden at run time and only kept in this process' environment.
set -uo pipefail

HERE=$(dirname "$(readlink -f "$0")")
STATE=${TRACE_STATE:-$HOME/.hermes/trace-dashboard}
HERMES=${HERMES_HOME:-$HOME/.hermes}
DEV=${TRACE_DEV_SSH:-ubuntu@192.168.56.108}
OWNER=${TRACE_OWNER:-ScuraUrsa}
DATA_REPO=${TRACE_DATA_REPO:-ScuraUrsa/hermes-default-workspace}
DATA_REF=${TRACE_DATA_REF:-claude/project-thread-cj9bvu}
BWS_SERVER=${BWS_SERVER_URL:-https://vault.bitwarden.eu}
PY=${TRACE_PYTHON:-python3}
mkdir -p "$STATE/www" "$STATE/in"

log() { echo "$(date -u +%FT%TZ) $*"; }

# GitHub token: Bitwarden secret GITHUB_TOKEN (same lookup as the bws git credential helper).
if [ -z "${GITHUB_TOKEN:-}" ] && [ -s "$HOME/.bws_token" ] && command -v bws >/dev/null; then
  GITHUB_TOKEN=$(BWS_ACCESS_TOKEN=$(cat "$HOME/.bws_token") bws secret list --server-url "$BWS_SERVER" -o json 2>/dev/null \
    | "$PY" -c 'import json,sys; print(next(s["value"].strip() for s in json.load(sys.stdin) if s["key"] == "GITHUB_TOKEN"))' 2>/dev/null) || GITHUB_TOKEN=""
  export GITHUB_TOKEN
fi
[ -n "${GITHUB_TOKEN:-}" ] || log "warn: no GITHUB_TOKEN, GitHub calls are anonymous (60/h)"

# Claude project threads (with prompt texts), exported by the project's Claude thread to an orphan data branch
# of a PRIVATE repo (this repo is public, so the data never goes here).
if curl -fsS --max-time 30 ${GITHUB_TOKEN:+-H "Authorization: Bearer $GITHUB_TOKEN"} \
     -H "Accept: application/vnd.github.raw" \
     "https://api.github.com/repos/$DATA_REPO/contents/claude_threads.json?ref=$DATA_REF" -o "$STATE/in/claude_threads.json.tmp"; then
  mv "$STATE/in/claude_threads.json.tmp" "$STATE/in/claude_threads.json"
else
  log "warn: could not fetch claude_threads.json, keeping the last copy"
fi

# Dev VM (kanban workers): its sessions and Claude Code runs, best effort. Its kanban board is already
# mirrored to prod as kanban-dev.db every minute.
if ssh -o BatchMode=yes -o ConnectTimeout=5 "$DEV" true 2>/dev/null; then
  if ssh -o BatchMode=yes "$DEV" "python3 - --dump-hermes --hermes-home dev=\$HOME/.hermes" \
       < "$HERE/collect.py" > "$STATE/in/dev_sessions.json.tmp"; then
    mv "$STATE/in/dev_sessions.json.tmp" "$STATE/in/dev_sessions.json"
  fi
  ssh -o BatchMode=yes "$DEV" 'cat ~/.hermes/autonomy/claude_runs.jsonl 2>/dev/null' > "$STATE/in/dev_claude_runs.jsonl.tmp" \
    && mv "$STATE/in/dev_claude_runs.jsonl.tmp" "$STATE/in/dev_claude_runs.jsonl"
else
  log "warn: dev VM $DEV unreachable, using the last copy of its sessions"
fi

"$PY" "$HERE/collect.py" \
  --hermes-home "prod=$HERMES" \
  --hermes-json "dev=$STATE/in/dev_sessions.json" \
  --kanban "dev=$HERMES/kanban-dev.db" --kanban "prod=$HERMES/kanban.db" \
  --claude-runs "prod=$HERMES/autonomy/claude_runs.jsonl" --claude-runs "dev=$STATE/in/dev_claude_runs.jsonl" \
  --claude-threads "$STATE/in/claude_threads.json" \
  --budget "$HERMES/autonomy/budget.json" \
  --pricing "${TRACE_PRICING:-$HERE/pricing.json}" \
  --owner "$OWNER" --days "${TRACE_DAYS:-120}" \
  --github-cache "$STATE/github-cache.json" \
  --out "$STATE/www/trace.json" || exit 1
cp "$HERE/web/index.html" "$STATE/www/index.html"
log "ok"
