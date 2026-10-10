# video-digest (ytdigest)

Hermes watches YouTube for Filip. Point it at a video and it writes a Notion page:
what the video is about, what was said, what was shown on screen, how to use it in
life, suggested actions, tags, chapters with clickable times, quotes, related topics,
the link and the full transcript. Songs and other artistic videos are only listed.

Notion: **Hermes Organized → YouTube Digest: Hermes zamiast oglądania → Raporty wideo**
(data source `561ac2c0-89c5-4d5a-aa40-67ab0f248e9c`).

## How a video is processed

```
link ─► yt-dlp metadata ─► music rule ──(artistic)──► Notion row "Artystyczne", stop, $0
                              │
                              ▼
                 transcript: uploaded captions ─► Groq Whisper turbo ─► Parakeet (CPU)
                             ─► local Whisper ─► YouTube auto-captions
                              │
                              ▼
                 cheap classifier (video type, artistic?)  ─► routing table (vbench)
                              │
          ┌───────────────────┴────────────────────┐
          ▼                                        ▼
  gemini_url (opt-in, paid): Gemini reads  frames (default): Ollama Cloud models
  the YouTube URL, audio + frames,         ffmpeg scene keyframes + dedupe (+ OCR)
  writes the report in one call            ─► vision model captions ─► text model report
          └───────────────────┬────────────────────┘
                              ▼
        bundle.json + report.json + report.md  ─► Notion page (template below)
```

Model choice per video type comes from the benchmark thread's `vbench/routing.json`
(same repo). Until it exists, `ytdigest/routing.py` uses `deepseek-v4.1-flash` (report),
`gpt-oss:120b` (classify) and `gemma4:31b` (vision, falls back to `glm-5.3-flash`; retired models are skipped using the live model list) on Ollama Cloud,
which Filip's plan already covers. The Gemini URL path is paid per token, so it only runs
with `gemini_enabled: true` in the config.

## Report template (Notion page body)

1. 📌 **Raport z filmu:** one sentence
2. O czym jest ten film
3. Co zostało powiedziane
4. Co było widać (+ key frames with captions)
5. Najważniejsze punkty
6. Jak możesz to wykorzystać w swoim życiu
7. Propozycje działań (checkboxes)
8. Rozdziały (clickable times)
9. Cytaty
10. Powiązane tematy do sprawdzenia
11. Tagi i metadane (channel, duration, type, transcript source, models, cost)
12. Film (embedded player + link)
13. ▸ Pełny transkrypt (toggle, a paragraph per minute with clickable times)

`report_language: en` switches headings and text to English.

## Ways to start it

| Where | How |
|---|---|
| Any Hermes chat | "Hermes, podsumuj <link>" (skill `youtube-digest`) |
| Claude Code on the VM | `/yt-digest <link>` |
| Terminal | `ytdigest run <link>` |
| Phone, one tap | Share → **HTTP Shortcuts** "Hermes digest" → `POST http://<vm-tailscale-ip>:8765/digest` |
| PC browser, one click | bookmark `javascript:window.open('http://<vm-tailscale-ip>:8765/digest?token=<T>&url='+encodeURIComponent(location.href))` |
| Backlog | cron `ytdigest-backlog-sync` daily 04:30 queues every playlist; cron `ytdigest-idle` every 30 min processes it when the VM is idle |

The one-click endpoint is `ytdigest serve`, run by `hermes/systemd/ytdigest-serve.service`
on the Tailscale address only, with `YTDIGEST_TOKEN` from Bitwarden.

## The idle backlog

`ytdigest worker --idle-only` checks before every video (`ytdigest gate` shows it):

- quota governor mode is not `idle` (`~/.hermes/autonomy/quota.json`)
- `budget.py can-afford` says Hermes' own self-work budget has room
- ytdigest's backlog spend today is under `backlog_daily_cap_usd` (default $1)
- no live session from Filip in the last 20 minutes, none of his kanban tasks (priority 100) running
- load per CPU ≤ 0.7 and ≥ 1.5 GB RAM free

It runs at `nice 19` / `ionice idle`, stops as soon as one check fails, and always
serves Filip's own queued links (priority 100) first, without the gate.
Every model call is priced into `~/.hermes/ytdigest/spend.jsonl` (tag `manual` or `backlog`).

## Install on a Hermes VM

```bash
git clone … hermes-enhancements && bash hermes-enhancements/video-digest/hermes/install.sh
```

Needs in `~/.hermes/.env` (from Bitwarden): `NOTION_API_KEY`, `GEMINI_API_KEY`
(only if `gemini_enabled`), `GROQ_API_KEY` (transcripts without captions), `OLLAMA_API_KEY`
(fallback models), `YTDIGEST_TOKEN` (one-click endpoint). Watch Later needs that
account's cookies at `~/.hermes/ytdigest/cookies/<account>.txt`.

## Tests

```bash
pip install -e '.[dev]' && pytest -q      # no network; ffmpeg needed for the frame tests
```

## Claude (subscription) routing

`topic_routes` in the config sends AI/software videos (keyword score over title,
tags, description and transcript start, `ytdigest/topics.py`) and links Filip sends
himself to `claude-code:sonnet` for both frame descriptions and the report. Calls
go through the Claude Code CLI with the subscription login (any `ANTHROPIC_API_KEY`
is removed from its environment), cost $0, and are logged in `spend.jsonl` with
input/output/cache tokens and Claude's own API-price estimate (`api_equiv_usd`).
Everything else stays on Ollama Cloud. Add `off: true` to a route to disable it.

## Compare models

```bash
ytdigest compare --refs claude-code:sonnet,claude-code:haiku --file ten.txt --notion-parent <page id>
```

Same videos, same frames and prompts, one model per run for both frame
descriptions and the report (no fallback). Writes `compare/<stamp>/results.json`
and `comparison.md` (tokens in/out/cache, API-equivalent $, seconds, frames
captioned) and, with `--notion-parent`, a Notion page with both reports per video.

## Transcript cleanup

YouTube auto captions have no punctuation. With `clean_auto_transcript` (default
on), a cheap model punctuates the one-minute paragraphs that go into Notion; the
timestamps stay, and any batch the model mangles is kept raw.

## "Processed" playlist

Every finished (non-artistic) video is added to the private playlist
`processed_playlist.title` on `processed_playlist.account` (default fjkazmierczak,
"Przetworzone przez Hermesa"), created on first use. The YouTube API cannot read or
change Watch Later, so removing videos from it is done in the browser. The Google
token comes from `~/.hermes/google-accounts/<alias>/google_token.json` or env
`GOOGLE_<ALIAS>_TOKEN_JSON` and needs the full `youtube` scope.

## Claude Desktop

`ytdigest/mcp_bridge.py` is a dependency-free MCP server for Claude Desktop on the
PC. It calls `ytdigest serve` on the VM (`/digest`, then `/report`) over Tailscale
and returns the report, so "summarise this video: <link>" works in any Claude
Desktop chat. Setup is in the file's docstring.

### Sonnet vs Haiku (10-video test, 2026-10-10)

Same transcript and frames, Claude doing classify, frames and report. API-price
equivalent: Sonnet $0.75/video ($1.82 per video hour), Haiku $0.33/video ($0.79/h).
Haiku was not faster, skipped frames in 3 of 10 videos and returned broken JSON
once; it is generic on screens, slides and code but fine on talking heads. Hence
`claude_light`: AI/software talking heads (podcast, interview, news, vlog) go to
Haiku, everything else on the Claude route and Filip's own links stay on Sonnet.
One 5-hour subscription window held ~45-50 Sonnet digests of 20-30 min videos.
