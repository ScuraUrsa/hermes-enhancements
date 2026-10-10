#!/bin/bash
# Install or update ytdigest on a Hermes VM (idempotent). Run as the Hermes user:
#   bash video-digest/hermes/install.sh [--with-local-asr] [--no-cron]
# Puts: venv ~/.hermes/ytdigest/venv, skill ~/.hermes/skills/media/youtube-digest,
# cron scripts ~/.hermes/scripts/ytdigest_*.sh, Claude Code command ~/.claude-code/commands/yt-digest.md,
# and two no-agent Hermes cron jobs. Secrets are NOT touched: NOTION_API_KEY, GEMINI_API_KEY,
# GROQ_API_KEY and OLLAMA_API_KEY must already be in ~/.hermes/.env (from Bitwarden).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
H="$HOME/.hermes"
LOCAL_ASR=0; CRON=1
for a in "$@"; do
  case "$a" in --with-local-asr) LOCAL_ASR=1 ;; --no-cron) CRON=0 ;; esac
done

command -v ffmpeg >/dev/null || { echo "ffmpeg missing (apt-get install ffmpeg)"; exit 1; }
mkdir -p "$H/ytdigest/cookies" "$H/scripts" "$H/skills/media/youtube-digest"
chmod 700 "$H/ytdigest/cookies"

[ -f "$H/ytdigest/config.yaml" ] || install -m 0644 "$HERE/config.example.yaml" "$H/ytdigest/config.yaml"
[ -x "$H/ytdigest/venv/bin/python" ] || python3 -m venv "$H/ytdigest/venv"
"$H/ytdigest/venv/bin/pip" install -q --upgrade pip
extras=""; [ "$LOCAL_ASR" = 1 ] && extras="[local-asr]"
"$H/ytdigest/venv/bin/pip" install -q --upgrade "$HERE$extras"
# vbench (same repo) supplies the stage prompts and the routing table the benchmark picked
if [ -f "$HERE/../vbench/pyproject.toml" ]; then
  "$H/ytdigest/venv/bin/pip" install -q --upgrade "$HERE/../vbench"
fi
# keep the routing table current: config points at the checked-out vbench/routing.json
if [ -f "$HERE/../vbench/routing.json" ] && [ -f "$H/ytdigest/config.yaml" ]; then
  sed -i "s|^routing_file:.*|routing_file: \"$(cd "$HERE/.." && pwd)/vbench/routing.json\"|" "$H/ytdigest/config.yaml"
fi
# yt-dlp needs a JS runtime (deno) for YouTube; without it many downloads fail with HTTP 403.
DENO_VERSION="${DENO_VERSION:-2.4.5}"
if ! command -v deno >/dev/null && [ ! -x "$HOME/.local/bin/deno" ]; then
  echo "installing deno $DENO_VERSION to ~/.local/bin"
  tmp="$(mktemp -d)"
  curl -fsSL -o "$tmp/deno.zip" "https://github.com/denoland/deno/releases/download/v${DENO_VERSION}/deno-x86_64-unknown-linux-gnu.zip"
  python3 -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$tmp/deno.zip" "$tmp"
  mkdir -p "$HOME/.local/bin" && install -m 0755 "$tmp/deno" "$HOME/.local/bin/deno"
  rm -rf "$tmp"
fi

install -m 0644 "$HERE/hermes/skills/youtube-digest/SKILL.md" "$H/skills/media/youtube-digest/SKILL.md"
install -m 0755 "$HERE/hermes/scripts/ytdigest_idle.sh" "$H/scripts/ytdigest_idle.sh"
install -m 0755 "$HERE/hermes/scripts/ytdigest_backlog_sync.sh" "$H/scripts/ytdigest_backlog_sync.sh"
CC_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude-code}"
mkdir -p "$CC_DIR/commands" && install -m 0644 "$HERE/claude-code/commands/yt-digest.md" "$CC_DIR/commands/yt-digest.md"

if [ "$CRON" = 1 ]; then
  HERMES="$H/hermes-agent/venv/bin/hermes"
  existing="$("$HERMES" cron list --all 2>/dev/null || true)"
  grep -q "ytdigest-idle" <<<"$existing" || \
    "$HERMES" cron create "every 30m" --name ytdigest-idle --script ytdigest_idle.sh --no-agent --deliver local
  grep -q "ytdigest-backlog-sync" <<<"$existing" || \
    "$HERMES" cron create "30 4 * * *" --name ytdigest-backlog-sync --script ytdigest_backlog_sync.sh --no-agent --deliver local
fi
"$H/ytdigest/venv/bin/ytdigest" status
echo "ytdigest installed. Try: $H/ytdigest/venv/bin/ytdigest run <youtube link>"
