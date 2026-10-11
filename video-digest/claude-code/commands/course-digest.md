---
description: Map an online course website and digest its lessons (text, files, speech, screen) into Notion "Kursy: lekcje"
argument-hint: <course link> [--limit N] [--model claude-code:sonnet]
allowed-tools: Bash(~/.hermes/ytdigest/venv/bin/sitedigest:*), Bash(set -a*)
---

Run sitedigest for: $ARGUMENTS

1. `set -a; . ~/.hermes/.env; set +a; ~/.hermes/ytdigest/venv/bin/sitedigest status` and check whether
   this site has a session (`logged_in`). If not, stop and tell Filip the three ways to log in from
   ~/.hermes/skills/media/course-digest/SKILL.md (cookies.txt is the quickest).
2. `~/.hermes/ytdigest/venv/bin/sitedigest map "<link>"` and show the outline counts and sections.
3. `~/.hermes/ytdigest/venv/bin/sitedigest digest <site> --limit <N, default 3> [--model ...]`, then
   `~/.hermes/ytdigest/venv/bin/sitedigest course <site>`.
4. Report in 6 lines or fewer: lessons found and digested, the course one-liner, 3 key points, the
   Notion link, and anything that failed (DRM videos, files that would not download).

Do not write the summaries yourself; the tool's output is the source. Never print cookie values.
