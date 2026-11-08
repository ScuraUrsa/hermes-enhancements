# course-harvest (PC side of sitedigest for login-gated course platforms)

Some course platforms can't be crawled from the VM: Zanfia (akademiasaas.pl) logs in
with an emailed code kept by Firebase in the browser, lists lessons only in React
state, and serves videos from Bunny Stream with signed, expiring links. course-harvest
runs on Filip's Windows PC, where he logs in once, and hands the VM a ready
sitedigest site folder (`~/.hermes/sitedigest/<site>/`).

```
PC (Windows, Chrome profile D:\courses\.profile-zanfia, GTX 1650 Ti)       dev VM
harvest_zanfia.py map        all products -> map.json (sitedigest format)
harvest_zanfia.py download   per lesson: text.md + signed link -> yt-dlp
                             (3 parallel) -> pages/<key>/prefetch/video.mp4
transcribe_pc.py --watch     faster-whisper large-v3-turbo on the GPU
                             -> prefetch/video.pl.vtt (~8-11x real time)
whimsical.py                 linked Whimsical mind maps: branches expanded,
                             screenshot -> pages/<key>/shot.jpg
sync_to_vm.sh                new files only (tar over ssh) ----------->  merge_map.py (map.lock)
pipeline_loop.sh             sync every 3 min + keeps the pool up ----->  sitedigest pool --workers 3
                                                                          --follow --require-vtt
requeue.py (on the VM)       send lessons back to the pool, e.g. after a mind map was added
push_notion.py (on the VM)   lesson reports + one overview per course -> Notion "Kursy: lekcje"
```

The login never leaves the PC: only lesson text and media go to the VM. Videos are
referenced in the map as `local:prefetch/video.mp4`; sitedigest uses a `.vtt` next to
the file as the transcript. Licence: Akademia SaaS regulamin § 6 allows saving the
content on the buyer's own devices for personal use. DRM-protected players are not
circumvented (none on Zanfia/Bunny so far).

## Setup (PC)

```powershell
python -m venv D:\hermes\course-harvest\venv
D:\hermes\course-harvest\venv\Scripts\python -m pip install -r requirements-pc.txt
# Whisper model: the Hugging Face cache download stalls on this PC, so fetch the files directly
#   https://huggingface.co/mobiuslabsgmbh/faster-whisper-large-v3-turbo -> models\faster-whisper-large-v3-turbo\
```

## Run (one course)

```powershell
venv\Scripts\python harvest_zanfia.py map                    # Chrome opens; log in once
venv\Scripts\python harvest_zanfia.py download --course akademia-globalnego-startupu --parallel 3
venv\Scripts\python transcribe_pc.py --course akademia-globalnego-startupu --watch
venv\Scripts\python whimsical.py --course akademia-globalnego-startupu
bash pipeline_loop.sh akademiasaas-pl 192.168.56.108 3      # sync + VM pool
```

Notes from the first run (Od Developera Do Foundera 3.0, 199 lessons / 34 h; Akademia
Globalnego Startupu, 178 lessons / 33 h):
- Bunny players can take >15 s to appear; the harvester waits up to 45 s.
- Lesson tabs: "Opis lekcji" is captured; "Notatki" (personal notes) and "Zapytaj kurs"
  (AI chat) are not course content. Extra material is linked: Whimsical maps (97 lessons)
  and shared Google Sheets (exported by sitedigest).
- Sonnet: ~80-100 s per lesson; 3 workers -> one lesson every ~30 s; the 5-hour Claude
  session limit is the real cap (the pool pauses until the reset).
- PyAV 19 (Python 3.14) dropped `metadata_errors`, which faster-whisper 1.2 passes;
  transcribe_pc.py strips it.

## Transcript quality (measured 2026-10-12)

`asr_bench.py` transcribes YouTube talks that have human-made captions with exactly this
pipeline and computes the word error rate (WER). Six Polish TEDx talks (~2 h):
2.5 / 5.2 / 5.2 / 6.8 % on clear speech, 12 % on a casual talk full of names, 21 % on a
talk whose captions are an edited translation (not verbatim). Most differences are
harmless (numbers as digits, word endings, filler words); meaning-changing errors are
~1-2 % of words: surnames, rare words, noisy passages.

Course jargon was the weak spot ("SaaS" -> "sas"/"sasa" about a third of the time,
"churn" -> "czern"), so each course gets ASR settings in
`D:\courses\<site>\asr\<course-slug>.json` (examples in `asr-examples/`):

```json
{"hotwords": "SaaS, churn, MRR, ...", "corrections_from": ["_common_corrections.json"], "corrections": {}}
```

- `hotwords`: course terms passed to Whisper. On two ODDF lessons misspelled jargon went
  22 -> 9 and 15 -> 8 at no extra time. The same list as `initial_prompt` did nothing (22 -> 20).
- `corrections`: whole-word replacements after transcription, only for spellings that
  never occur in Polish (`czern` -> `churn`, `sasie` -> `SaaS-ie`).
- `glossary.py --course X` lists candidate terms (titles, text under the videos) and
  English-looking words in the current transcripts, to curate the file.
- `transcribe_pc.py --redo` re-transcribes lessons made before the settings (old VTT kept as
  `*.vtt.v1`, marker `*.vtt.asr2`; `sync_to_vm.sh` sends the new VTT along with its marker).
  `--fix-only` applies just the corrections without the GPU.
- `asr_check.py --course X` transcribes the first minutes of 3 lessons with turbo and with
  large-v3 (3-4x slower) and measures how much they disagree; above 10 % use large-v3 for
  that course.

## One command for any YouTube video, playlist or channel (2026-11-07)

`digest.py URL [URL ...] [--model claude-code:sonnet|haiku] [--max 50] [--notify]` runs the same path as the
courses: yt-dlp on the PC (480p, ffmpeg + deno from WinGet; the VM is blocked by YouTube) -> text.md with
description and chapters -> transcript from YouTube's human subtitles, else faster-whisper on the GPU with
`D:\courses\youtube\asr\default.json` -> sync to dev -> `sitedigest pool` -> Notion "Kursy: lekcje"
(Strona = youtube) + an overview for playlists/channels. It waits for the dev VM when prod_guard has paused it.

Hermes: skill `media/video-digest` (`hermes/video-digest/SKILL.md`) -> `~/.hermes/scripts/digest_request.py`
(`hermes/digest_request.py`) writes `~/.hermes/digest-queue/new/<job>.json` on prod -> Windows task
"Hermes digest queue" (every 10 min, `digest_queue.cmd`) -> `digest_queue.py` -> `digest.py --notify` ->
done/<job>.json + a phone/Matrix push with the Notion link. The runner also checks once a day that the
Claude CLI on dev is logged in and pushes Filip the login command if not. Claude Code skill:
`claude-skill-video-digest.md` (installed as `D:\hermes\.claude\skills\video-digest\SKILL.md`).
