# ROADMAP — Hermes Enhancements

## Faza 1: Quick Wins (ten tydzień)

### 1.1 Playwright MCP
- [ ] Zainstaluj Node.js + npm (jeśli brak)
- [ ] `npm install -g @playwright/mcp`
- [ ] `hermes mcp add playwright --command "npx @playwright/mcp"`
- [ ] Przetestuj: browser_navigate, click, type, snapshot
- [ ] POV: automatyczne wypełnianie formularzy

### 1.2 ElevenLabs TTS
- [ ] Pobierz API key z Bitwarden (`ELEVENLABS_API_KEY`)
- [ ] `hermes config set tts.provider elevenlabs`
- [ ] Przetestuj: `/voice tts` → "Cześć, tu Hermes"
- [ ] POV: porównanie jakości Edge vs ElevenLabs

### 1.3 Docker Sandbox
- [ ] Sprawdź czy Docker działa: `docker run hello-world`
- [ ] `hermes config set terminal.backend docker`
- [ ] Przetestuj: `terminal("ls /")` — czy działa w kontenerze?
- [ ] POV: bezpieczne uruchamianie kodu

## Faza 2: Średnioterminowe (2-4 tygodnie)

### 2.1 Mem0 Memory
- [ ] Zainstaluj Mem0: `pip install mem0ai`
- [ ] Skonfiguruj jako memory backend
- [ ] Przetestuj cross-session memory

### 2.2 Qdrant RAG
- [ ] Zainstaluj Qdrant (Docker)
- [ ] Pipeline: dokumenty → embedding → Qdrant
- [ ] Zintegruj z Hermesem przez custom tool

### 2.3 CrewAI Orchestration
- [ ] Zainstaluj CrewAI: `pip install crewai`
- [ ] Stwórz crew: Researcher + Coder + Reviewer
- [ ] Zintegruj z Hermesem

### 2.4 Real-time Voice Pipeline
- [ ] Groq Whisper (STT) + ElevenLabs (TTS)
- [ ] WebSocket server
- [ ] Integracja z Notification Bridge

## Faza 3: Długoterminowe (1-3 miesiące)

### 3.1 E2B Sandbox
### 3.2 LangGraph Workflows
### 3.3 Home Assistant Integration
### 3.4 Mobile Native App

## Metryki sukcesu

- [ ] 3+ POV z działającymi prototypami
- [ ] Wszystkie POV przetestowane na hermes-vm
- [ ] Dokumentacja "kopiuj-wklej" dla każdego
- [ ] Commity na GitHub (ScuraUrsa/hermes-enhancements)
