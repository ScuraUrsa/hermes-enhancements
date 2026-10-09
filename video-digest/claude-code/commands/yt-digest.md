---
description: Digest a YouTube video into the Notion "Raporty wideo" database (transcript + visuals + summary)
argument-hint: <youtube link> [more links...]
allowed-tools: Bash(~/.hermes/ytdigest/venv/bin/ytdigest:*), Bash(set -a*)
---

Run the ytdigest pipeline for: $ARGUMENTS

1. If there is exactly one link, run
   `set -a; . ~/.hermes/.env; set +a; ~/.hermes/ytdigest/venv/bin/ytdigest run "<link>" --json`
   and wait for it (1-5 minutes).
2. If there are several links, queue them with
   `~/.hermes/ytdigest/venv/bin/ytdigest add --now <links...>` and say the idle worker
   will pick them up within 30 minutes.
3. Report back in 5 lines or fewer: the one-line summary, the 3 most useful key points,
   and the Notion link. For status "artistic" say it was only listed. For "failed",
   quote the error and the fix from the skill's Problems table
   (~/.hermes/skills/media/youtube-digest/SKILL.md).

Do not write the summary yourself; the tool's output is the source.
