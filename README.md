# 🔥 Hermes Enhancements — Research & POV

**Sesja MAX TOKEN BURN — 19 Lipca 2026**

Kompleksowy research możliwości wzmocnienia Hermes Agent + 3 działające Proof of Value.

## Struktura

```
hermes-enhancements/
├── README.md                    # Ten plik
├── matrix.md                    # Macierz Impact/Effort (17 ulepszeń)
├── ROADMAP.md                   # Rekomendowana kolejność wdrożeń
├── research/                    # Szczegółowy research
│   ├── mcp-servers.md           # 9800+ serwerów MCP, top 15
│   ├── coding-agents-comparison.md  # Claude Code vs Codex vs Cursor vs Aider
│   ├── voice-ai.md              # ElevenLabs, Whisper, Voice Agents
│   ├── browser-automation.md    # Playwright MCP, Selenium, Browser Use
│   ├── memory-systems.md        # Mem0, Qdrant, ChromaDB, Zep
│   ├── multi-agent-frameworks.md # CrewAI, LangGraph, AutoGen
│   ├── visual-orchestration.md  # n8n, Flowise, LangFlow
│   ├── home-assistant.md        # HA + Wyoming + Hermes
│   ├── code-sandbox.md          # E2B, Docker, Modal
│   └── mobile-edge.md           # Mobile app, Raspberry Pi
└── POV/                         # Proof of Value (działające prototypy)
    ├── 01-elevenlabs-tts/       # ✅ ElevenLabs TTS (działa!)
    │   ├── README.md
    │   └── demo.py
    ├── 02-browser-automation/   # ✅ Selenium + Chrome (działa!)
    │   ├── README.md
    │   └── demo.py
    └── 03-mem0-memory/          # ✅ Mem0 koncepcja (offline demo)
        ├── README.md
        └── demo.py
```

## Top 3 — Zrób teraz (HIGH Impact + LOW Effort)

### 1. ElevenLabs TTS (Impact: 8, Effort: 4) ✅ POV gotowy
Zamień Edge TTS na ElevenLabs. API key już jest w Bitwarden.
```bash
hermes config set tts.provider elevenlabs
```

### 2. Playwright MCP / Selenium (Impact: 9, Effort: 3-5) ✅ POV gotowy
Pełna automatyzacja przeglądarki. Selenium działa na Python 3.10.
Playwright MCP wymaga Node.js (niedostępne bez sudo).

### 3. Docker Sandbox (Impact: 8, Effort: 4) ⚠️ Docker bez uprawnień
Docker jest zainstalowany, ale brak uprawnień do socketa.
Wymaga `sudo usermod -aG docker $USER` lub root.

## Kluczowe znaleziska

### Hermes vs konkurencja
- **Hermes wygrywa**: self-improving skills, multi-platform gateway, memory, provider-agnostic
- **Konkurencja wygrywa**: 1M context (Claude), sandboxed VMs (Codex), parallel agents (Cursor)

### MCP — 9800+ serwerów
- Playwright MCP, GitHub MCP, PostgreSQL MCP — największy impact
- Hermes ma natywny MCP client (`hermes mcp add`)

### Voice AI
- ElevenLabs 11.ai (Marzec 2026) — voice assistant zarządzający workflow
- Groq Whisper — najszybszy STT, free tier

### Memory
- Mem0 (~55k GitHub stars) — automatyczna ekstrakcja faktów
- Qdrant (3ms latency, 99.2% recall) — najlepszy open-source vector DB

### Multi-Agent
- CrewAI (45k stars, 5.3M downloads/mo) — role-based, najszybszy prototyping
- LangGraph (25k stars, 38.8M downloads/mo) — graph-based, production-ready

## Ograniczenia VM (hermes-vm)

- Python 3.10 (nie 3.11+) — browser-use, Open WebUI niedostępne
- Brak sudo — Node.js, Docker permissions niedostępne
- Brak Docker permissions — sandbox niedostępny
- Chrome dostępny — Selenium działa

## Rekomendowana ścieżka

1. **Ten tydzień**: ElevenLabs TTS, Selenium plugin, Mem0 (jeśli API key)
2. **2-4 tygodnie**: CrewAI orchestration, Qdrant RAG, Real-time Voice
3. **1-3 miesiące**: E2B sandbox, LangGraph, HA integration

## Commity

Wszystkie zmiany w repo: https://github.com/ScuraUrsa/hermes-enhancements
