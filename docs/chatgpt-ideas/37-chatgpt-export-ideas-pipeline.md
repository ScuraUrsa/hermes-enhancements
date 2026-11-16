# 37 · Back up ChatGPT history and turn it into readable files and plans

**Status vs Hermes:** already done. `~/.hermes/scripts/chatgpt_export_watch.py` (hourly cron, plus `chatgpt_export_remind.sh`) watches Gmail for the "export ready" mail of all three accounts. The link needs a ChatGPT login, so it asks Filip to drop the zip on Google Drive, then unzips it into `~/hermes-data/chatgpt-exports/<account>/<date>` and starts the Claude Code run that produced this doc set.
**Priority:** P5

## Goal and context
Filip wanted all his ChatGPT chats saved locally for backup and recovery, and a parser that turns the official JSON export into readable files that look like the web UI. He also noticed that the export download link is session-bound and fails outside the browser.

Source: kazmierczakfilipjan, *Chat backup options* (2026-02-04).

## Architecture (as built, plus one gap)
```
ChatGPT export e-mail → watcher sees it in Gmail → Filip downloads the zip (session-bound link) → Google Drive folder
  → chatgpt_export_watch.py → unzip per account/date → Claude Code: ideas → this repo (plans only)
gap: a readable archive (one markdown file per conversation, following current_node branch)
```

## Implementation plan
1. Optional: add a `render` step that writes one markdown file per conversation (title, date, messages in order along `current_node`) into a private, non-git folder under `~/hermes-data`, and index it in Obsidian for search.
2. Keep the conversations out of all repos; only plans and summaries go to git.

## Deployment plan / Configuration / Cost
Existing scripts; free.

## Open questions
- Is a human-readable archive wanted, or is the raw export plus this idea index enough?
