# 32 · Hermes access to Filip's YouTube account (transcribe, summarise, Watch Later)

**Status vs Hermes:** mostly done. `video-digest/` (`ytdigest`: YouTube → Notion), skills `youtube-account-archive`, `youtube-content`, `youtube-digest`, WOBI `youtube_history.py`, and roadmap goal C4 (the @scuraursa archive with Whisper). Possibly missing: write access (adding to playlists).
**Priority:** P4

## Goal and context
Filip wanted Hermes to transcribe and summarise any video he likes, and to add videos to Watch Later, without giving it his Google password. He asked about Composio as an integration layer, and how to keep login data in Bitwarden.

Source: kazmierczakfilipjan, *YouTube Agent Access Setup* (2026-06-21), *Problem z playlistą WL* (2026-07-18).

## Architecture
Google OAuth with the narrowest YouTube Data API scope, a token stored in Bitwarden Secrets Manager, and the existing digest pipeline. No password sharing and no Composio (a third party would hold the token).
Note: the YouTube API no longer allows reading or writing the **Watch Later** list. Use a normal private playlist ("Hermes queue") instead.

## Implementation plan
1. Check which scopes the current `ytdigest` token has. If read-only, decide whether write (`youtube` scope) is worth it.
2. If yes: a "Hermes queue" private playlist. A Matrix/phone share → Hermes adds the video and queues a digest.
3. Document in the skill why Watch Later is not supported.

## Deployment plan
Existing video-digest deployment; token via `gacct`/BWS.

## Configuration
OAuth client, scope list, playlist id.

## Cost / hardware
Free (API quota 10k units/day is plenty).

## Open questions
- Is write access wanted at all, given that the link-inbox already queues videos?
