# Macierz Impact/Effort — Wszystkie znaleziska

## Legenda
- **Impact**: 1-10 (jak bardzo wzmocni Hermesa)
- **Effort**: 1-10 (jak trudne do wdrożenia)
- **Cost**: $ (darmowe), $$ (tanie), $$$ (drogie)
- **Priority**: HIGH (zrób teraz), MEDIUM (zrób wkrótce), LOW (nice to have)

## Macierz

| # | Ulepszenie | Impact | Effort | Cost | Risk | Priority |
|---|-----------|--------|--------|------|------|----------|
| 1 | **Playwright MCP + Hermes** | 9 | 3 | $ | npm required | 🔴 HIGH |
| 2 | **ElevenLabs TTS + Hermes** | 8 | 4 | $ | API key już jest | 🔴 HIGH |
| 3 | **Docker sandbox** | 8 | 4 | $ | Docker już jest | 🔴 HIGH |
| 4 | **Mem0 memory backend** | 7 | 5 | $ | API key needed | 🟡 MEDIUM |
| 5 | **Qdrant RAG pipeline** | 8 | 6 | $ | Wymaga instancji | 🟡 MEDIUM |
| 6 | **CrewAI orchestration** | 8 | 5 | $ | Nowy framework | 🟡 MEDIUM |
| 7 | **GitHub MCP** | 6 | 3 | $ | gh CLI już działa | 🟡 MEDIUM |
| 8 | **Real-time Voice Pipeline** | 9 | 6 | $$ | WebSocket, Groq | 🟡 MEDIUM |
| 9 | **E2B sandbox** | 7 | 6 | $$ | API key needed | 🟢 LOW |
| 10 | **LangGraph workflow** | 7 | 7 | $ | Stroma krzywa | 🟢 LOW |
| 11 | **n8n orchestration** | 6 | 5 | $ | Overlap z cron | 🟢 LOW |
| 12 | **HA Voice brain** | 7 | 6 | $ | Brak HA instancji | 🟢 LOW |
| 13 | **PostgreSQL MCP** | 5 | 3 | $ | Rzadko potrzebne | 🟢 LOW |
| 14 | **Slack MCP** | 5 | 3 | $ | Gateway już ma | 🟢 LOW |
| 15 | **Notion MCP** | 6 | 4 | $ | API key już jest | 🟢 LOW |
| 16 | **Mobile native app** | 5 | 8 | $ | Gateway działa | 🟢 LOW |
| 17 | **Edge AI (RPi)** | 4 | 7 | $$ | Hardware needed | 🟢 LOW |

## Top 3 — Zrób teraz (HIGH Impact + LOW Effort)

### 1. Playwright MCP + Hermes (Impact: 9, Effort: 3)
**Co**: Pełna automatyzacja przeglądarki przez MCP
**Dlaczego**: Obecny browser tool jest ograniczony. Playwright MCP daje self-healing, multi-step, lepsze snapshoty.
**Jak**: `npm install -g @playwright/mcp && hermes mcp add playwright`
**Koszt**: Darmowe (open source)
**Ryzyko**: npm + Node.js wymagane

### 2. ElevenLabs TTS + Hermes (Impact: 8, Effort: 4)
**Co**: Zamiana Edge TTS na ElevenLabs
**Dlaczego**: Jakość głosu 10x lepsza, emotion detection, voice cloning
**Jak**: `hermes config set tts.provider elevenlabs` + API key z Bitwarden
**Koszt**: Free tier dostępny
**Ryzyko**: API rate limits na free tier

### 3. Docker Sandbox (Impact: 8, Effort: 4)
**Co**: Izolowane wykonywanie komend w Dockerze
**Dlaczego**: Bezpieczeństwo — kod agenta nie dotyka hosta
**Jak**: `hermes config set terminal.backend docker`
**Koszt**: Darmowe (Docker już jest)
**Ryzyko**: Docker musi być zainstalowany i działać

## Top 5 — Zrób wkrótce (MEDIUM)

### 4. Mem0 Memory Backend (Impact: 7, Effort: 5)
### 5. Qdrant RAG Pipeline (Impact: 8, Effort: 6)
### 6. CrewAI Orchestration (Impact: 8, Effort: 5)
### 7. GitHub MCP (Impact: 6, Effort: 3)
### 8. Real-time Voice Pipeline (Impact: 9, Effort: 6)
