---
name: youtube-digest
description: "Watch a YouTube video for Filip: transcript + what is shown on screen -> summary, tags, life applications, full transcript, written to the Notion database 'Raporty wideo'. Use when Filip sends a YouTube link with 'digest', 'podsumuj', 'streść', 'przeanalizuj', 'obejrzyj za mnie', '/yt', or asks to queue videos or check the YouTube backlog."
platforms: [linux]
prerequisites:
  env_vars: [NOTION_API_KEY]
---

# YouTube digest (ytdigest)

The work is done by the `ytdigest` CLI, not by you. Never summarise a video yourself
from the title or your memory: run the tool and report what it produced.

Binary: `~/.hermes/ytdigest/venv/bin/ytdigest` (alias below: `ytd`).
Env comes from `~/.hermes/.env` (NOTION_API_KEY, GEMINI_API_KEY, GROQ_API_KEY, OLLAMA_API_KEY).

## One video, now (Filip asked)

```bash
set -a; . ~/.hermes/.env; set +a
~/.hermes/ytdigest/venv/bin/ytdigest run "<youtube link>" --json
```

- Takes 1-5 minutes. Run it in the background with notify_on_complete if your
  terminal tool supports it, and tell Filip you started.
- Reply with: the `one_line` sentence, 3-5 key points from `report_md`, and the
  `notion_url`. Do not paste the whole report.
- `status: "artistic"` means music/art: say it was listed under "Artystyczne" and not analysed.
- `status: "failed"`: give the `error` in one sentence. "Sign in to confirm" / "bot" errors
  mean YouTube is blocking the VM: suggest refreshing cookies (see Problems).

## Several links, or "later"

```bash
~/.hermes/ytdigest/venv/bin/ytdigest add <link> <link> ...          # backlog, processed when idle
~/.hermes/ytdigest/venv/bin/ytdigest add --now <link> ...            # next worker run, no idle wait
```

## Backlog questions

```bash
~/.hermes/ytdigest/venv/bin/ytdigest status     # queue counts and today's spend
~/.hermes/ytdigest/venv/bin/ytdigest gate       # why the idle worker is or isn't running
~/.hermes/ytdigest/venv/bin/ytdigest backlog-sync --account koalamis6   # re-read playlists now
```

The idle worker runs from the no-agent cron job `ytdigest-idle` (every 30 min) and
only works when: quota mode is not idle, budget.py can afford it, the ytdigest daily
backlog cap (config `backlog_daily_cap_usd`) is not spent, Filip has had no live
session for 20 min, none of his kanban tasks run, and the VM has spare CPU/RAM.

## Problems

| Symptom | Fix |
|---|---|
| `NOTION_API_KEY not set` | it lives in Bitwarden; re-run the env sync |
| `GEMINI_API_KEY not set` in the log | only happens with `gemini_enabled: true`; the tool falls back to frames + Ollama models. Gemini is off by default because it is paid |
| `Sign in to confirm you're not a bot` | export fresh YouTube cookies to `~/.hermes/ytdigest/cookies/<account>.txt` (Netscape format) |
| `refresh failed for <account>` | Google token expired: `~/.hermes/scripts/google_auth_queue.sh` |
| a video stuck in "processing" | the next worker run releases it after 2 h |

Docs: Notion page "YouTube Digest: Hermes zamiast oglądania" (Hermes Organized).
Code: ScuraUrsa/hermes-enhancements, folder `video-digest/`.
