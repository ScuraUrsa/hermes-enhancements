# vbench

Finds the cheapest model that is good enough for each kind of YouTube video (podcast, coding tutorial,
lecture, vlog, music...), for each step of Hermes' video-report pipeline, and writes the answer to
`routing.json`. Design and metrics: [DESIGN.md](DESIGN.md).

Standard library only (Python 3.11+). Building bundles needs `yt-dlp[default]` and ffmpeg.

## Run it on the Hermes VM

```bash
cd hermes-enhancements/vbench
export OLLAMA_API_KEY=...          # Ollama Cloud
export CLAUDE_SETUP_TOKEN=...      # `claude setup-token` (subscription); the claude CLI must be installed
export GEMINI_API_KEY=...          # optional: Gemini-with-URL candidates
export GROQ_API_KEY=...            # optional: transcription candidates

# 1. sample: dump playlists, sort by type, pick ~30 videos
yt-dlp --flat-playlist -J --cookies koalamis6.txt "https://www.youtube.com/playlist?list=WL" > pl-wl.json
python3 -m vbench sample pl-*.json -o sample.json

# 2. bundles (transcript, frames, audio) and answer keys
python3 -m vbench bundle sample.json --root bundles --cookies koalamis6.txt --account koalamis6
python3 -m vbench label --bundles bundles --labels labels --model claude-code:opus
python3 -m vbench review --labels labels -o labels/REVIEW.md   # check, then set "reviewed": true
python3 -m vbench check --matrix matrix.toml

# 3. the sweep (resumable; run stage by stage to spread quota)
python3 -m vbench run matrix.toml --stage classify
python3 -m vbench run matrix.toml --stage transcribe
python3 -m vbench run matrix.toml --stage vision
python3 -m vbench run matrix.toml --stage report --stage video_url

# 4. leaderboard + routing table for the pipeline
python3 -m vbench route results/sweep-1 -o routing.json --md LEADERBOARD.md
```

## Files

| Path | What |
|---|---|
| `vbench/bundle.py` | `bundle.json` format shared with the pipeline (`video_bundle/v1`) |
| `vbench/prompts.py` | stage prompts (also used by the pipeline), judge prompts, JSON parsing |
| `vbench/providers.py` | adapters: Ollama Cloud and other OpenAI-compatible APIs, `claude -p`, Anthropic API, Gemini with a video URL |
| `vbench/stages.py` | classify, vision, report (with map-reduce for long transcripts), URL baseline |
| `vbench/transcribe.py` | speech-to-text track (WER against human captions) |
| `vbench/scoring.py` | per-type weights, judge calls, scores |
| `vbench/runner.py` | the matrix runner (parallel, resumable, two judges) |
| `vbench/route.py` | leaderboard and `routing.json` |
| `providers.toml` | providers, API-equivalent prices, context sizes |
| `matrix.toml` | the first sweep |
| `routing.json` | the table the pipeline reads (provisional until the first sweep) |

Model refs are `provider:model[@option=value,...]`, e.g. `ollama-cloud:qwen3-vl:235b-instruct`,
`claude-code:haiku@effort=low`, `gemini-video:gemini-2.5-flash-lite@fps=0.2`, `ollama-cloud:deepseek-v4-flash@frames=none`.

Tests: `python3 -m pytest` (no network, no keys).
