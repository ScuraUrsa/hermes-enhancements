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
  gemini_url (default): Gemini reads       frames (fallback, or chosen by routing):
  the YouTube URL, audio + frames,         ffmpeg scene keyframes + dedupe (+ OCR)
  writes the report in one call            ─► vision model captions ─► text model report
          └───────────────────┬────────────────────┘
                              ▼
        bundle.json + report.json + report.md  ─► Notion page (template below)
```

Model choice per video type comes from the benchmark thread's `vbench/routing.json`
(same repo). Until it exists, `ytdigest/routing.py` uses cheap defaults: Gemini
Flash-Lite for the URL path, `deepseek-v4.1-flash` / `gpt-oss:120b` / `gemma3:27b` (vision, falls back to `gemma3:12b`) on
Ollama Cloud for the fallback path.

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
(main path), `GROQ_API_KEY` (transcripts without captions), `OLLAMA_API_KEY`
(fallback models), `YTDIGEST_TOKEN` (one-click endpoint). Watch Later needs that
account's cookies at `~/.hermes/ytdigest/cookies/<account>.txt`.

## Tests

```bash
pip install -e '.[dev]' && pytest -q      # no network; ffmpeg needed for the frame tests
```
