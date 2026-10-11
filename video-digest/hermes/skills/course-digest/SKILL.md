---
name: course-digest
description: "Go through an online course or documentation website for Filip: log in, map every module and lesson, download videos and files, and write a report per lesson (page text + files + speech + what is on screen) plus a course overview into the Notion database 'Kursy: lekcje'. Use when Filip sends a course/platform link with 'przerób kurs', 'zmapuj', 'przeanalizuj kurs', 'course digest', '/kurs', sends a cookies.txt for a site, or asks how far the course backlog is."
platforms: [linux]
prerequisites:
  env_vars: [NOTION_API_KEY]
---

# Course digest (sitedigest)

The work is done by the `sitedigest` CLI (installed with ytdigest), not by you. Never
summarise a course from its title or your memory: run the tool and report what it produced.

Binary: `~/.hermes/ytdigest/venv/bin/sitedigest` (alias below: `sd`). Env: `set -a; . ~/.hermes/.env; set +a`.
Everything for one site lives in `~/.hermes/sitedigest/<site>/` (session, map, downloads, reports).
The site name is derived from the link (`academy.example.com` -> `example-com`); pass `--site` to choose one.

## 1. Log in (once per site; again when the session expires)

Pick the first that works:
- **Filip sends a cookies.txt** (browser extension "Get cookies.txt LOCALLY", exported while logged in):
  `sd import-cookies /path/cookies.txt --url "<course link>"`. Delete the uploaded copy afterwards.
- **Password in Bitwarden**: put `SITEDIGEST_<SITE>_USER` / `SITEDIGEST_<SITE>_PASSWORD` in `~/.hermes/.env`
  (site name upper-cased, `-` -> `_`), then `sd login "<link>" --auto`. Fails on captcha/2FA: use cookies.
- **Visible browser** (Filip at a desktop with the tool, or `ssh -X` to the VM): `sd login "<link>"`, he logs in, presses Enter.

Never print, paste or send cookie or password values. Session files are mode 600; keep them that way.

## 2. Map the site

```bash
sd map "<course or platform link>" [--include "/courses/abc"] [--max-pages 800]
```
- Opens pages one by one (1.5-3.5 s apart), GET only. It never opens logout, cart, checkout,
  delete, unenrol or "mark complete" links.
- Prints the outline: sections, lessons, how many videos and files. Send Filip the counts and the
  section list (not every lesson) and ask nothing: digesting starts by itself (step 3) unless he said only map.
- `--include REGEX` limits it to one course on a platform with many. Re-running continues where it stopped.
- "redirected to the login page" = session expired: back to step 1.

## 2b. Download now when player links expire

Some platforms (Zanfia, Bunny Stream) sign each video link for minutes. Then run
`sd fetch <site> [--include "<course or module>"]` right after mapping, on the machine that holds
the login; it re-opens each page and downloads videos and files immediately (no model calls).
Digest later reuses the files.

## 3. Digest lessons

Filip asked for it now:
```bash
sd digest <site> --limit 5            # first 5 lessons not done yet, in course order
sd digest <site> --model claude-code:sonnet   # AI/software courses: Sonnet via the subscription
sd course <site>                      # course overview once lessons are done
```
Run long jobs in the background with notify_on_complete. Reply with the overview's `one_line`,
3-5 key points and the Notion link.

Otherwise leave it to the `sitedigest-idle` cron: it digests 4 lessons per run, only while Hermes
is idle (same gate as the YouTube backlog), and writes the course overview after the last lesson.

Per lesson the report has: what it teaches, what was shown (frames, slides, screenshots), key
points, how to use it, to-dos, tools/resources with links, downloaded files, prerequisites, level,
quotes, and the source material (page text, transcripts, file text) in toggles.

## Status

`sd status` -> per site: pages mapped, lessons left, digested, failed, videos, files, cost.

## Problems

| Symptom | Fix |
|---|---|
| `SessionExpired` / login page | Step 1 again (cookies expire; some sites log out other devices) |
| video `drm` | Widevine-protected stream (e.g. some Udemy lectures). Not downloaded on purpose; the lesson is digested from text, files and captions. |
| video `download_failed` with 403 | Player wants the page as Referer (sent already) or a fresh session: re-login, then `sd digest <site> --page <key> --redo` |
| `got an HTML page instead of a file` | File behind a viewer page; the link is still listed in the report |
| Chromium does not start | `sudo ~/.hermes/ytdigest/venv/bin/playwright install-deps chromium` (admin, once) |
| `site.notion_data_source_id not set` | `sd notion-setup --parent <Notion page id>`, put the id in `~/.hermes/ytdigest/config.yaml` under `site:` |

Courses Filip bought are for his own use: keep reports and downloads private (Notion private
workspace, VM disk), never publish or share them.
