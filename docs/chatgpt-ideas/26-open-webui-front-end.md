# 26 · Open WebUI as a front-end for Hermes (decision doc)

**Status vs Hermes:** partly exists, then stopped. Open WebUI ran with the CrewAI stack and was stopped and its volume archived on 2026-10-06 (WOBI `docker/POST_SETUP_OPEN_WEBUI.md`, `scripts/openwebui-backup/`). An untracked `openwebui-bridge/hermes_bridge.py` in `~/hermes-enhancements` exposes Hermes to an Open WebUI Pipe (still set to a retired model). Hermes has its own OpenAI-compatible API server on 127.0.0.1:8642.
**Priority:** P4

## Goal and context
Filip used Open WebUI as the chat UI for CrewAI and Ollama models and wanted to:
- use it as the front-end for agents, multi-user, with per-user web-search settings;
- know why web search used only 3 of 30 pages (retrieval top-k, not the search);
- install tools/functions/pipes as code instead of clicking, so redeploys are repeatable;
- enable channels, import an old DB, and know whether `hermes gateway` supports Open WebUI (it does, via the OpenAI-compatible API);
- compare it to LobeHub.

Source: kazmierczakfilipjan.
- *Open WebUI vs LobeHub* (2026-02-03), *WebUI darmowe modele AI* (2026-03-07), *Open WebUI CrewAI Setup* (2026-03-04)
- *User Customization of LLMs*, *Open Web UI Browsing*, *LLM Retrieval Limits*, *WebUI Dependency Issue* (2026-03-10)
- *Automating Plugin Installation*, *Import Open WebUI DB*, *LiteLLM as Proxy* (2026-03-16)
- *OpenWebUI Search Issues* (2026-05-18), *Hermes Gateway Open WebUI* (2026-05-29)

## Architecture
If it comes back, keep it thin:
```
browser / phone (tailnet only) → Open WebUI (container, SSO via Tailscale identity headers)
   → connection: Hermes API server :8642 (OpenAI-compatible)  ← no bridge script needed
   web search: Open WebUI's own (SearXNG self-hosted), top-k raised, or "bypass embedding" for full pages
   plugins: functions/tools stored as files in git, loaded at start by a small init job via the Open WebUI API
```

## Implementation plan
1. **Decide first:** Matrix + the Hermes TUI + HA voice may already cover chat. Bring Open WebUI back only if a browser UI with history and file upload is really missing.
2. If yes: point Open WebUI straight at the Hermes API server and delete the untracked bridge (or commit it if the Pipe adds something, such as streaming tool output).
3. Plugins as code: `openwebui/functions/*.py` in git plus an init script that upserts them through the API on each deploy.
4. Web search: SearXNG container; set result count and top-k explicitly. Document why "3 sources" happens.

## Deployment plan
A WOBI role with docker compose, restore from the 2026-10-06 archive only if the old chats matter.

## Configuration
`OPENAI_API_BASE_URL` = Hermes API, `ENABLE_CHANNELS`, search engine settings, admin account from Bitwarden.

## Cost / hardware
~1 GB RAM. Free.

## Open questions
- Is a web chat UI still wanted after Matrix went live?
- Should the untracked `openwebui-bridge/` be committed or removed? It sits in the main checkout, not in git.
