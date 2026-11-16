---
name: video-digest
description: "Full digest of YouTube videos, playlists or channels into Notion reports (transcript + frames + Sonnet), run by the PC pipeline. Use when Filip asks to opracować / przerobić / zrobić raport / nauczyć się z filmu, playlisty, kanału or course."
platforms: [linux]
---

# Video digest (Filip, 2026-11-07)

Filip's standard way to "watch" videos through Hermes. The heavy work (download, GPU transcript, Sonnet
report with key frames, Notion page) runs on his PC and the dev VM, not in this agent. You only queue the job
and report back.

## When to use

- Filip sends a YouTube link (video, playlist, channel) and asks to opracować, przerobić, zrobić raport,
  wyciągnąć wiedzę, "obejrzyj za mnie", nauczyć się, or to put it in Notion.
- Several links or a whole playlist/channel ("ostatnie 20 filmów z kanału X": pass the channel URL and `--max 20`).

Use the lighter `youtube-content` skill instead only when he wants a quick answer in chat right now
("streść w 3 zdaniach", "o czym jest ten film?") and no report.

## How

```bash
~/.hermes/scripts/digest_request.py URL [URL ...] [--model sonnet|haiku] [--max N] [--note "why"]
```

- Default model: sonnet (best reports). Use `--model haiku` only when Filip asks for cheap/fast.
- It prints a job id. Tell Filip in one line: queued, he will get a phone/Matrix notification with the Notion
  link when it is ready. Short videos take 10-30 min; the dev VM sleeps at night for the prod upgrade, so a
  job queued in the evening may finish the next afternoon.
- Status when he asks: `~/.hermes/scripts/digest_request.py --status [JOB]` (shows Notion links when done).

## Where the results are

Notion "Kursy: lekcje" database (https://www.notion.so/e44ec7c6c4fc4f92af0a8626144963d4), Strona = youtube,
Sekcja = playlist/channel. A playlist or channel also gets an overview page.

## Do not

- Do not download or transcribe videos yourself on the VM (YouTube blocks the VM; the PC has the GPU).
- Do not put Claude subscription tokens anywhere; the pipeline uses the Claude CLI on dev.
- Courses on paid platforms (Akademia SaaS etc.) are not YouTube: tell Filip to ask Claude Code on the PC
  (course-harvest), they need his browser login.
