# AI Coding Agents — Porównanie (Lipiec 2026)

## Liderzy rynku

| Tool | Architektura | Context | SWE-bench | Cena | Best For |
|------|-------------|---------|-----------|------|----------|
| **Claude Code** | Terminal agent | 1M tokenów | 80.9% | API ($) | Deep refactors, architektura |
| **Codex CLI** | Sandboxed VM, async | 400K tokenów | 77.3% (Terminal-Bench) | $20/mo flat | Background tasks, PR delivery |
| **Cursor 3** | IDE + cloud agents | ~200K tokenów | — | $20/mo | Daily flow, parallel agents |
| **Aider** | Terminal, git-first | Repo map | — | Free (OS) | Open-source, model-agnostic |
| **Cline** | VS Code extension | Context dep. | — | Free (OS) | Stepwise planning |
| **Roo Code** | VS Code extension | Context dep. | — | Free (OS) | Multi-mode workflows |
| **Hermes Agent** | Terminal + gateway | Model dep. | — | Free (OS) | Self-improving, multi-platform |

## Co konkurencja robi lepiej niż Hermes

### Claude Code
- **1M token context** — może zjeść cały codebase
- **Hook system** — custom hooks i slash commands
- **Agent SDK** — budowanie programatycznych agentów
- **Sub-agenty** — parallel task execution

### Codex CLI
- **Sandboxed VM** — bezpieczne uruchamianie kodu
- **Async execution** — "fire and forget", wraca z PR
- **Multi-agent v2** — parallel task execution
- **Image inputs** — screenshots, wireframes, diagrams

### Cursor 3
- **10 parallel agents** — na jednego usera
- **Cloud agents** — działają gdy laptop śpi
- **Design Mode** — visual work
- **TypeScript SDK** — programmatic orchestration

### Aider
- **Model-agnostic** — działa z każdym LLM
- **Tree-sitter repo map** — inteligentne rozumienie codebase
- **Architect mode** — two-model workflow
- **Auto git commits** — z sensownymi message'ami

## Co Hermes robi lepiej niż konkurencja

1. **Self-improving skills** — żaden inny agent nie uczy się z doświadczenia
2. **Multi-platform gateway** — Telegram, Discord, Slack, WhatsApp, iMessage, Signal...
3. **Persistent memory** — cross-session, pluggable backends
4. **Provider-agnostic** — 20+ providerów, credential pooling
5. **Profiles** — izolowane instancje
6. **Cron + webhook** — natywny scheduling
7. **Kanban** — multi-agent work queue
8. **MCP native** — wbudowany MCP client

## Wnioski dla Hermesa

**Rzeczy do zaadaptowania od konkurencji:**

1. **Sandboxed execution** (od Codex) — Docker/E2B sandbox dla bezpiecznego uruchamiania kodu
2. **Hook system** (od Claude Code) — custom hooks przed/po tool call
3. **Repo map** (od Aider) — tree-sitter do rozumienia struktury codebase
4. **Cloud agents** (od Cursor) — background agents na zdalnych VM
5. **Architect mode** (od Aider) — dwa modele: planista + wykonawca

**Rzeczy gdzie Hermes wygrywa i powinien to podkreślać:**
- Learning loop (skills) — unikalna przewaga
- Multi-platform — najszersze pokrycie
- Memory system — dojrzały i pluggable
