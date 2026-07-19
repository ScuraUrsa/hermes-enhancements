# Multi-Agent Frameworks — Research (Lipiec 2026)

## Porównanie frameworków

| Framework | GitHub Stars | PyPI Downloads/mo | License | Architektura |
|-----------|-------------|-------------------|---------|-------------|
| **LangGraph** | 25.8k | 38.8M | MIT | Graph-based (low-level) |
| **CrewAI** | 45.4k | 5.3M | MIT | Role-based (high-level) |
| **AutoGen** | 55.3k | ~1.3M | CC-BY-4.0 | Conversational (maintenance) |
| **OpenAI Agents SDK** | ~15k | ~2M | MIT | Lightweight, async |
| **Google ADK** | ~8k | ~500k | Apache 2.0 | Google-native |
| **Swarms** | 5.8k | 23K | Apache 2.0 | Swarm intelligence |

## Charakterystyka

### LangGraph — "Power tool"
- **Model**: Directed graph, nodes = functions, edges = state transitions
- **Mocne**: Persistence, streaming, durable execution, human-in-the-loop
- **Słabe**: Stroma krzywa uczenia, overkill dla prostych workflow
- **Użytkownicy**: Klarna, Replit, Elastic
- **Dla kogo**: Złożone stateful workflow, multi-step z approval

### CrewAI — "Role-based"
- **Model**: Role → Agents → Crews → Tasks
- **Mocne**: Intuicyjny, szybki prototyping, dobre docs
- **Słabe**: Mniej kontroli nad niskopoziomową egzekucją
- **Dla kogo**: Szybkie multi-agent prototypy, "team of specialists"

### AutoGen — "Conversational"
- **Model**: Agent-to-agent conversation
- **Mocne**: Dojrzały, duża społeczność
- **Słabe**: Maintenance mode (ostatni update: Sep 2025), CC-BY-4.0 license
- **Dla kogo**: Legacy projekty, research

### OpenAI Agents SDK — "Lightweight"
- **Model**: Async agents, handoffs, guardrails
- **Mocne**: Prosty, szybki, OpenAI-native
- **Słabe**: Vendor lock-in (OpenAI)
- **Dla kogo**: OpenAI ecosystem

## Hermes Multi-Agent obecnie

Hermes ma wbudowane:
- **delegate_task** — spawn subagentów (single + batch)
- **Kanban** — multi-agent work queue (SQLite)
- **Profiles** — izolowane instancje agentów
- **Cron** — scheduled agent runs
- **tmux spawning** — manual multi-agent coordination

## Rekomendacje

### POV #7: CrewAI + Hermes
- CrewAI jako warstwa orchestracji nad Hermesem
- Hermes jako "worker agent" w CrewAI crew
- Role: Researcher, Coder, Reviewer, DevOps
- **Impact: 8/10, Effort: 5/10**

### POV #8: LangGraph + Hermes
- LangGraph dla złożonych, stateful workflow
- Hermes jako node w LangGraph
- Human-in-the-loop approval
- **Impact: 7/10, Effort: 7/10** (stroma krzywa uczenia)

### Ulepszenia istniejącego multi-agent
- Hermes już ma solidny multi-agent (delegate_task, kanban)
- Brakuje: wizualnego podglądu agentów, lepszego handoffu
- CrewAI może dodać role-based orchestration
- LangGraph może dodać stateful workflow
