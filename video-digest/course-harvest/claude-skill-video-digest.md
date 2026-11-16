---
name: video-digest
description: Digest YouTube videos, playlists, channels or online-course sites into Notion reports with Filip's proven pipeline (PC download + GPU transcript, Sonnet on the dev VM, Notion). Use whenever Filip asks to opracować / przerobić / zrobić raport z / nauczyć się z filmu, playlisty, kanału or kursu.
---

# Video digest (Filip, 2026-11-07: "robimy")

Always use this path for "process this video/playlist/channel/course". It is the one measured and fixed on
1100+ Akademia SaaS lessons and the Watch Later videos (transcript WER 2.5-7 %, glossaries, frames, Notion).

## YouTube (video, playlist, channel)

On the PC (Git Bash or PowerShell):

```
D:\hermes\course-harvest\venv\Scripts\python.exe D:\hermes\course-harvest\digest.py URL [URL ...] ^
    [--model claude-code:sonnet|claude-code:haiku] [--max 50] [--notify] [--no-wait]
```

- Steps: yt-dlp lists and downloads (480p, ffmpeg + deno from WinGet) -> text.md (title, channel, date,
  description, chapters) -> transcript: YouTube's human subtitles if any, else faster-whisper on the GPU with
  `D:\courses\youtube\asr\default.json` -> sync to dev -> `sitedigest pool` (2 workers) -> Notion
  "Kursy: lekcje" (Strona = youtube) + overview for playlists/channels. Last stdout line = JSON with links.
- Long jobs: run it in the background (`run_in_background`) and report the links when it finishes.
- `--notify` sends Filip a phone/Matrix push with the Notion link (timeplane `tp_push` on prod).
- Default model sonnet. Haiku only if Filip asks or after his verdict in task T218 says otherwise.
- Hermes queues the same jobs: `~/.hermes/scripts/digest_request.py` on prod -> Windows task
  "Hermes digest queue" (every 10 min) -> `digest_queue.py` -> `digest.py --notify`. To queue instead of
  running here: `ssh ... ubuntu@192.168.56.107 '~/.hermes/scripts/digest_request.py URL'`.

## Course sites with a login (Akademia SaaS = Zanfia, others)

`D:\hermes\course-harvest\` (README in hermes-enhancements `video-digest/course-harvest/`):
`harvest_zanfia.py map|download` (Chrome profile `D:\courses\.profile-zanfia`, Filip logs in once) ->
`transcribe_pc.py` (glossary per course in `D:\courses\<site>\asr\`) -> `pipeline_loop.sh` (sync + pool) ->
`push_notion.py` on dev (lessons + one overview per course, from ALL lessons). A new platform needs a new
harvester; never bypass DRM, keep to the platform's terms (personal use).

## Known constraints (check before promising times)

- Dev VM (192.168.56.108) is paused at night by prod_guard for the prod upgrade (often until ~09:00-15:00
  local). digest.py waits for it (up to 36 h). Never wake dev while a prod-upgrade replica runs (prod first).
- Claude CLI on dev must be logged in under `CLAUDE_CONFIG_DIR=~/.claude-code`. The queue runner checks daily
  and pushes Filip the login command if not. Login only he can do:
  `ssh -t -i D:\hermes\terraforge-stacks\local\generated\id_rsa ubuntu@192.168.56.108 "CLAUDE_CONFIG_DIR=~/.claude-code claude"` then `/login`.
- Notion key is on prod only; scripts pipe it prod -> dev in memory. Never print it.
- Dev disk: videos are pruned after digest; `sync_to_vm.sh` holds videos back below 15 GB free.
- Progress: `D:\hermes\course-harvest\regen_status.cmd` (v2 rebuild), VM `pool.log`, `sitedigest pool SITE --stats`.
