# POV #11: Langfuse Monitoring Integration

**Status**: ✅ Działa  
**Impact**: 8 | **Effort**: 3 | **Cost**: $ (open-source, free tier)

## Co to jest?

Langfuse to open-source'owa platforma do observability LLM — tracing, monitoring, evaluation.  
POV #11 integruje Langfuse z Hermes Agent, umożliwiając śledzenie każdego tool calla, generacji LLM i metryk sesji.

## Architektura

```
Hermes Agent
  └─ tool call (web_search, terminal, browser, ...)
       └─ HermesTracer.tool_span()
            ├─ Langfuse Cloud / Self-hosted (gdy API keys)
            └─ Local JSON fallback (~/.hermes/langfuse_traces/)
```

Hierarchia:
- **Trace** = sesja Hermesa (1 konwersacja)
- **Span** = pojedynczy tool call (np. `web_search`, `terminal`)
- **Generation** = wywołanie LLM (prompt → completion)
- **Score** = metryki (success rate, latency, token usage)

## Szybki start

### Opcja A: Langfuse Cloud (zalecana)

```bash
# 1. Zarejestruj się na https://cloud.langfuse.com
# 2. Skopiuj API keys z Settings → API Keys

export LANGFUSE_PUBLIC_KEY="pk-..."
export LANGFUSE_SECRET_KEY="sk-..."
export LANGFUSE_HOST="https://cloud.langfuse.com"

# 3. Uruchom demo
cd POV/11-langfuse-monitoring
python3 demo.py
```

### Opcja B: Self-hosted Langfuse

```bash
# Docker (jeśli dostępny):
docker run -p 3000:3000 langfuse/langfuse

export LANGFUSE_PUBLIC_KEY="pk-..."
export LANGFUSE_SECRET_KEY="sk-..."
export LANGFUSE_HOST="http://localhost:3000"

python3 demo.py
```

### Opcja C: Local-only (bez serwera)

```bash
python3 demo.py --local
# Traces zapisywane w ~/.hermes/langfuse_traces/*.json
```

## Demo output

```
============================================================
🔍 Langfuse Monitoring — Hermes Agent Demo
============================================================
  ✅ [web_search] 312ms → ~/.hermes/langfuse_traces/..._tool_web_search.json
  ✅ [terminal] 512ms → ~/.hermes/langfuse_traces/..._tool_terminal.json
  ✅ [read_file] 105ms → ~/.hermes/langfuse_traces/..._tool_read_file.json
  ✅ [write_file] 210ms → ~/.hermes/langfuse_traces/..._tool_write_file.json
📤 Langfuse flushed

============================================================
📊 Session Summary
============================================================
  session_id: demo-abc123
  duration_seconds: 1.45
  tool_calls: 1
  total_tokens: 165
  errors: 0
  langfuse_connected: False
```

## Integracja z Hermes

```python
from demo import HermesTracer

tracer = HermesTracer(session_id="my-session")

# Trace tool call
with tracer.tool_span("web_search", {"query": "Langfuse docs"}) as span:
    result = search_web("Langfuse docs")
    span.output = result

# Trace LLM generation
tracer.generation(
    name="hermes-chat",
    model="deepseek-v4-pro",
    prompt="User message...",
    completion="Assistant response...",
    usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    latency_ms=850,
)

# Score session
tracer.score("success_rate", 1.0)
tracer.flush()
```

## Wymagania

- Python 3.10+
- `pip install langfuse`
- Langfuse API keys (dla cloud) lub self-hosted instancja

## Dashboard

Po podłączeniu do Langfuse Cloud, dashboard pokazuje:
- **Traces**: pełna historia sesji z timeline
- **Sessions**: grupowanie trace'y po session_id
- **Generations**: koszt, latency, token usage
- **Scores**: success rate, quality metrics
- **Alerts**: anomaly detection na latency i error rate

## Token monitor

Demo automatycznie nagrywa zużycie tokenów przez `ollama_token_monitor.py`:

```bash
python3 ~/workspace/hermes-enhancements/POV/04-token-monitor/ollama_token_monitor.py status
```
