# Visual Orchestration — Research (Lipiec 2026)

## Porównanie platform

| Platform | GitHub Stars | Język | AI-native | Best For |
|----------|-------------|-------|-----------|----------|
| **n8n** | ~60k | TypeScript | ✅ (AI Agents node) | Business automation + AI |
| **Flowise** | ~38k | TypeScript | ✅ | AI agent builder |
| **LangFlow** | ~45k | Python | ✅ | LLM app builder |
| **Dify** | ~65k | Python | ✅ | AI app platform |

## Charakterystyka

### n8n — "Business automation + AI"
- **Model**: Node-based workflow, 400+ integrations
- **AI Agents**: Native feature od late 2025
- **Mocne**: Multi-agent teams, agent-to-agent handoff, production-ready
- **Słabe**: Nie pure-AI (general automation)
- **Dla kogo**: Automatyzacja biznesowa z AI

### Flowise — "AI agent builder"
- **Model**: Visual drag-and-drop, AgentFlow V2 (2025)
- **Mocne**: Najbardziej dojrzały TypeScript-native visual AI builder
- **Słabe**: Mniej integracji biznesowych niż n8n
- **Dla kogo**: Czyste AI workflow

### LangFlow — "LLM app builder"
- **Model**: Visual LangChain builder
- **Mocne**: Python-native, LangChain ecosystem
- **Słabe**: Mniej AI-agent-focused niż Flowise
- **Dla kogo**: LangChain użytkownicy

## Hermes + Orchestration

Hermes ma wbudowane:
- **Cron** — scheduled workflows
- **Webhook** — event-driven triggers
- **Kanban** — task queue
- **delegate_task** — sub-agent spawning

**Brakuje**: Visual builder, drag-and-drop workflow

## Rekomendacja

### n8n + Hermes (webhook integration)
- n8n jako visual orchestration layer
- Hermes jako AI brain (przez webhook)
- n8n triggery → Hermes webhook → AI processing → n8n kontynuuje
- **Impact: 6/10, Effort: 5/10**

**Uwaga**: Hermes już ma solidne narzędzia orchestracyjne (cron, webhook, kanban). n8n dodaje visual builder, ale nie jest krytyczny.
