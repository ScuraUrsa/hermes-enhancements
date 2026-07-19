# POV #5: CrewAI + Hermes — Multi-Agent Orchestration

## Cel
Zintegrować CrewAI jako warstwę orchestracji nad Hermesem.

## Status
✅ crewai 1.15.4 zainstalowane
✅ Demo koncepcyjne gotowe
⚠️  Pełny test wymaga API calli (koszt tokenów)

## Szybki start

```bash
pip install crewai
cd ~/workspace/hermes-enhancements/POV/05-crewai-orchestration
python3 demo.py
```

## Architektura

```
CrewAI (orchestrator)
  ├── Researcher Agent → szuka informacji
  ├── Coder Agent → pisze kod
  ├── Reviewer Agent → sprawdza jakość
  └── Hermes Agent → wykonuje zadania systemowe (git, tests, deploy)
```

## Integracja z Hermesem

### Opcja A: CrewAI jako planner, Hermes jako executor
```python
# CrewAI planuje, Hermes wykonuje
crew = Crew(agents=[researcher, coder, reviewer], tasks=[...])
plan = crew.kickoff()

# Hermes wykonuje tool calls
hermes.execute(plan)
```

### Opcja B: Hermes tool w CrewAI
```python
# Hermes jako narzędzie dla CrewAI agentów
from crewai_tools import tool

@tool("hermes_execute")
def hermes_execute(command: str) -> str:
    """Execute a command through Hermes Agent."""
    # Wywołaj Hermesa przez CLI lub API
    pass
```

## Kluczowe zalety

- **Role-based**: intuicyjny model (Researcher, Coder, Reviewer)
- **Sequential/parallel**: elastyczne procesy
- **Tool integration**: każdy agent może używać narzędzi
- **Memory**: CrewAI ma wbudowaną pamięć konwersacji
- **Python 3.10+**: działa na tej VM

## Wnioski

- CrewAI to najszybsza ścieżka do multi-agent orchestration
- 45k GitHub stars, 5.3M downloads/mo — dojrzały ekosystem
- Idealne uzupełnienie Hermesa: CrewAI planuje, Hermes wykonuje
- Wymaga API key (Ollama Cloud działa jako OpenAI-compatible)
