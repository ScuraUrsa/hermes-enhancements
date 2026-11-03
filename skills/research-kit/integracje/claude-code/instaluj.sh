#!/usr/bin/env bash
# Install the bibliography hooks (K76) into the user's Claude Code settings (~/.claude/settings.json).
# Meant for the cloud environment's setup script, so every new session in the project checks links
# against the shared bibliography before WebFetch and records visits after it:
#   [ -f /mnt/project-files/bibliografia/kit/instaluj.sh ] && bash /mnt/project-files/bibliografia/kit/instaluj.sh || true
# Idempotent; never fails the setup (any error = message on stderr, exit 0).
# BIB_DIR (default /mnt/project-files/bibliografia) is the shared base; each session writes its own
# zdarzenia/claude-<session>.jsonl, because appends from several containers to one file on the
# network mount are not safe (last write wins).
set -uo pipefail
ZRODLO="$(cd "$(dirname "$0")" && pwd)"
BIB_DIR="${BIB_DIR:-/mnt/project-files/bibliografia}"
CEL="${HOME}/.claude/bib-hook"
mkdir -p "$CEL" "${HOME}/.claude" || exit 0
# bib.py sits next to this script in the kit copy, or in ../../skrypty in the repo.
BIB_PY="$ZRODLO/bib.py"; [ -f "$BIB_PY" ] || BIB_PY="$ZRODLO/../../skrypty/bib.py"
cp "$ZRODLO/bib_hook.py" "$BIB_PY" "$CEL/" || { echo "bib-hook: copy failed" >&2; exit 0; }
KOMENDA="BIB_DIR=$BIB_DIR BIB_WRITER=claude-\${CLAUDE_CODE_REMOTE_SESSION_ID:-\$(hostname)} python3 $CEL/bib_hook.py"
python3 - "$HOME/.claude/settings.json" "$KOMENDA" <<'PY' || echo "bib-hook: settings merge failed" >&2
import json, sys
from pathlib import Path
plik, komenda = Path(sys.argv[1]), sys.argv[2]
try:
    ust = json.loads(plik.read_text()) if plik.is_file() else {}
except ValueError:
    sys.exit("settings.json is not valid JSON, left untouched")
hooks = ust.setdefault("hooks", {})
for zdarzenie, matcher in (("PreToolUse", "WebFetch"), ("PostToolUse", "WebFetch|WebSearch")):
    lista = [w for w in hooks.get(zdarzenie, []) if "bib_hook.py" not in json.dumps(w)]
    lista.append({"matcher": matcher, "hooks": [{"type": "command", "command": komenda, "timeout": 15}]})
    hooks[zdarzenie] = lista
plik.write_text(json.dumps(ust, indent=2, ensure_ascii=False) + "\n")
PY
echo "bib-hook: installed (base $BIB_DIR)"
exit 0
