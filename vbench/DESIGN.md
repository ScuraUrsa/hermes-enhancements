# vbench: the cheapest good-enough model for each kind of video

Status: harness built and tested with mocks (2026-10-09). No real model has been run yet: the sample
needs the koalamis Google account re-authorised, and the run happens on the Hermes VM, which can reach
YouTube, Ollama Cloud and the Claude subscription.

## 1. The question

Filip wants Hermes to "watch" his YouTube backlog (mostly the koalamis account) and write a Notion report
per video: what it was about, what was said, what was shown, how to use it, tags, transcript, link.
Thousands of videos means the model choice is the cost. The benchmark answers, **per kind of video**:

1. Which model can **classify** a video (and spot music/art that should be skipped) most cheaply?
2. Which **vision** model describes frames well enough (slides, code, places)?
3. Which **report** model writes a report good enough to replace watching?
4. Is it cheaper to skip the pipeline and let **Gemini watch the URL** directly?
5. When there are no captions, which **speech-to-text** is good enough?

The output is `routing.json`, which the pipeline (`video-digest/`) reads.

## 2. Pipeline shape it measures

```
classify (text, cheap) ──► music_artistic? ── yes ──► list in Notion, stop
        │ no
        ▼
vision: frames ──► descriptions (per type: 0.5-4 frames/min)
        ▼
report: transcript + frame descriptions ──► JSON report ──► Notion page
        (long transcripts: condense in parts, then report)

alternative per type: Gemini with the YouTube URL ──► JSON report (no frames, no transcript needed)
```

The same prompts (`vbench/prompts.py`) are used by the pipeline, so what is measured is what runs.

## 3. Video types

`podcast_talk, interview, tutorial_screen, lecture_slides, explainer_visual, vlog_travel,
news_commentary, documentary, review_product, music_artistic, short, other`. These are also the values of
the "Typ wideo" select in the Notion "Raporty wideo" database. Types decide two things: the scoring weights
(the picture barely matters in a podcast and carries half the content in a coding tutorial) and the route.

## 4. Sample and answer keys

* **Sample** (`vbench sample`): dump Filip's playlists with `yt-dlp --flat-playlist -J`, let a cheap model
  sort titles into types, draw 3 per type (2 music) across short and long videos: about 30 videos.
  Mix Polish and English, with and without captions.
* **Bundles** (`vbench bundle`): yt-dlp + ffmpeg build the same `bundle.json` the pipeline builds (schema in
  `vbench/bundle.py`), plus the audio and every caption track for the transcription track. Frames are scene
  cuts at least 2 s apart plus one at least every 30 s, 768 px wide.
* **Answer keys** (`vbench label`, then `vbench review`): a strong model (Claude Opus via the subscription)
  drafts, per video, 8-15 **key points** with importance 1-3, **visual facts** that are only visible on screen
  (with times), tags, the type, and reference frame descriptions. Filip or Claude checks each key and sets
  `"reviewed": true`. Keys are lists of checkable facts, not prose, so a candidate can't win by sounding like
  the model that wrote the key.

## 5. Metrics

| Stage | Score (0-100) | Notes |
|---|---|---|
| classify | 100 type + art flag right, 60 only art flag right, 0 art flag wrong | calling a lecture "art" loses a whole report |
| transcribe | 100 x (1 - WER) on the first 10 min vs human captions | only videos with manual captions |
| vision | 60% visual-fact recall + 25% on-screen text accuracy + 15% no hallucination | judge compares with reference frame descriptions |
| report | weighted: key-point recall (importance-weighted), visual-fact recall, faithfulness (unsupported claims: -0.3 major, -0.1 minor), tag F1, usefulness 1-5 | invalid JSON or missing fields = 0 |

Report weights by type:

| | key points | visual | faithfulness | tags | usefulness |
|---|---|---|---|---|---|
| talk types (podcast, interview, news) | 0.50 | 0.05 | 0.25 | 0.10 | 0.10 |
| visual types (tutorial, lecture, explainer, vlog, review, documentary) | 0.35 | 0.30 | 0.15 | 0.10 | 0.10 |
| other | 0.40 | 0.20 | 0.20 | 0.10 | 0.10 |

If a video has no visual facts, the visual weight moves to key points.

**Judges.** Two judges from different families grade every vision and report output, and the scores are
averaged (`claude-code:sonnet` and `ollama-cloud:deepseek-v4-pro` by default). That cancels most
self-preference (a Claude judge favouring Claude reports); `judge_spread` in each row shows where they
disagree, which is where to look by hand.

**Isolation.** Report candidates get the answer key's frame descriptions by default, so a weak vision model
can't drag a good report model down; `@frames=none` variants test whether the picture is worth paying for
at all. The final route is then checked end to end.

**Cost.** Every call records tokens, time, and two costs:
* *marginal*: what Filip pays for this call. $0 on Ollama Cloud and the Claude subscription.
* *API-equivalent*: the list price of the same model on a pay-per-token API (`providers.toml`, from models.dev;
  Claude Code reports its own). Routing ranks by this, because subscriptions are quota-limited by compute,
  which tracks price, and a route stays cheap if a subscription is ever dropped.

## 6. Routing rule

Per stage and video type, a model is **good enough** when its mean score is at least the stage floor
(classify 90, transcribe 80, vision 65, report 70) **and** within 92% of the best model on that type, with
at most 10% failures. The cheapest good-enough model wins (latency breaks ties). For the report stage a
pipeline model also pays for its vision stage, while a Gemini-URL model does not, so the two compete on
total cost. A `default` entry pools all types (for unknown types). Fewer than 2 videos behind a choice marks
it `low_confidence`. Music/art is always `skip: true`.

`routing.json` today is a **provisional** prior (`"provisional": true`): cheap Ollama Cloud models known to
be capable, so the pipeline can start before the first sweep.

## 7. Candidates in the first sweep (`matrix.toml`)

* classify: gpt-oss:20b, nemotron-3-nano:30b, ministral-3:8b, deepseek-v4.1-flash (Ollama Cloud), Claude Haiku.
* vision: gemma3 12b/27b, gemma4 31b, ministral-3 14b, qwen3.5 397b, kimi-k2.6, gemini-3-flash-preview (all
  Ollama Cloud), Claude Haiku and Sonnet.
* report: gpt-oss:120b, nemotron-3-super, deepseek-v4.1-flash, glm-5.3-flash, deepseek-v4-pro, qwen3-next:80b, minimax-m2.7, glm-4.7,
  kimi-k2.6 (Ollama Cloud), Claude Haiku, Sonnet, Opus (the ceiling), plus two text-only variants.
* Gemini with the URL: 2.5 Flash-Lite at 0.2 and 1 fps, 3.1 Flash-Lite at 0.5 fps, 3 Flash at 1 fps (needs
  `GEMINI_API_KEY`).
* transcription: YouTube auto captions, Groq whisper-large-v3-turbo and whisper-large-v3.

All Ollama models are **Ollama Cloud** (Filip's choice: no local models). Claude runs through `claude -p` on
Filip's subscription.

## 8. What a run costs

About 30 videos x (5 classify + 9 vision + 13 report + 4 URL) = ~930 candidate calls plus ~1,300 judge calls.
Marginal cost: $0 for Ollama Cloud and Claude (subscription quota), Gemini a few cents (free tier covers 8 h
of video a day), Groq ~$0.04 per audio hour. Quota is the real limit, so run stages separately and let it
resume: `vbench run matrix.toml --stage classify`, then `vision`, then `report`.

## 9. Known limits

* Answer keys come from a Claude model; Filip's review and the second judge are the guard against bias.
* Ollama Cloud retires models without notice (qwen3-vl:235b-instruct went in October 2026 with HTTP 410).
  `vbench run` and `vbench check --matrix` ask the provider which models it still serves and skip the rest,
  so a retired model is reported, not scored 0. Routing entries carry a `vision_fallback` for the same reason.
* Frames per minute per type is a heuristic for now (0.5 talk, 1.5 default, 3 visual, 4 short); a later sweep
  can vary it with the same harness.
* Transcription WER uses only the first 10 minutes and only videos with human captions.
