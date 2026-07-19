# Research: MCP Servers, Hermes Plugins, Voice Pipeline
Data: 2026-07-19

## MCP Servers (Model Context Protocol)

**Repozytorium**: github.com/modelcontextprotocol/servers
- 88.6k gwiazdek, 11.3k forków, 908 kontrybutorów, 4138 commitów
- Ostatni release: 2026.7.10 (tydzień temu)
- Języki: TypeScript 70.7%, Python 18%, JavaScript 10.2%

**Dostępne serwery referencyjne**:
- `filesystem` — operacje na plikach (read, write, edit, search)
- `github` — GitHub API (issues, PR, repos, search)
- `postgres` — PostgreSQL queries
- `slack` — Slack messaging
- `git` — git operations
- `google-drive` — Google Drive access
- `everything` — all-in-one server
- `brave-search` — web search
- `memory` — knowledge graph memory
- `puppeteer` — browser automation
- `fetch` — HTTP requests

**MCP Registry**: registry.modelcontextprotocol.io — zastąpił starą listę third-party

**Jak dodać do Hermesa**:
```bash
hermes mcp add <name> --command "npx @modelcontextprotocol/server-<name>"  # TypeScript
hermes mcp add <name> --command "python3 -m mcp_server_<name>"             # Python
```

## Hermes Plugins

**System pluginów** (z dokumentacji hermes-agent.nousresearch.com):

Plugin to katalog w `~/.hermes/plugins/<name>/` z:
- `plugin.yaml` — manifest
- `__init__.py` — funkcja `register(ctx)`
- `schemas.py` — tool schemas
- `tools.py` — tool handlers

**Co plugin może robić**:
- `ctx.register_tool()` — dodaj tool
- `ctx.register_hook()` — hooki (pre/post tool call, pre/post turn)
- `ctx.register_command()` — slash commands (/nazwa)
- `ctx.register_cli_command()` — komendy CLI
- `ctx.inject_message()` — wstrzyknij wiadomość do konwersacji
- `ctx.register_platform()` — adapter gateway (Discord, Telegram, IRC)
- `ctx.register_image_gen_provider()` — backend generowania obrazów
- `ctx.register_video_gen_provider()` — backend generowania wideo
- `ctx.register_context_engine()` — kompresja kontekstu
- `ctx.register_skill()` — bundle skilli
- `ctx.llm.complete()` — wywołaj LLM przez hosta

**Top 10 pluginów (wg Composio)**:
1. Disk Cleanup — czyści tymczasowe pliki
2. Langfuse Observability — tracing, monitoring
3. Composio Connect — 1000+ SaaS przez OAuth
4. Kanban Dashboard — multi-agent task board
5. Google Meet — notatki ze spotkań
6. Honcho Memory — personalizacja
7. Hindsight Memory — knowledge graph
8. Hermes Achievements — statystyki użycia
9. Self-Evolution — optymalizacja skilli
10. Web Search Plus — lepsze wyszukiwanie

## Voice Pipeline

**ElevenLabs Conversational AI** (2026):
- Łączy STT + LLM + TTS w jedną sesję WebSocket
- Turn detection, session management, interruption handling
- Scribe v2 — STT z latency <300ms
- Eleven v3 TTS — najwyższa jakość głosu

**Alternatywy**:
- OpenAI Whisper — open-source, batch mode, nie real-time
- Groq Whisper — szybszy, API
- Deepgram — real-time STT
- CAMB.AI — konkurencyjna latencja

**Stack rekomendowany dla Hermesa**:
- STT: Groq Whisper (szybki, tani) lub ElevenLabs Scribe v2 (najlepsza jakość)
- TTS: ElevenLabs (już skonfigurowany)
- Transport: WebSocket
- Integracja: Hermes plugin `voice-pipeline`

## Rekomendacje do wdrożenia (POV)

### HIGH priority (zrób teraz):
1. **Composio Connect** — 1000+ SaaS, OAuth, zero konfiguracji
2. **Langfuse** — monitoring agenta (tokeny, latency, tracing)
3. **Disk Cleanup** — już wbudowany, wystarczy włączyć

### MEDIUM priority:
4. **Honcho/Hindsight Memory** — lepsza pamięć niż wbudowana
5. **Google Meet plugin** — notatki ze spotkań
6. **Voice Pipeline** — ElevenLabs Scribe v2 + WebSocket

### LOW priority:
7. **Self-Evolution** — optymalizacja skilli
8. **Web Search Plus** — lepsze wyszukiwanie
