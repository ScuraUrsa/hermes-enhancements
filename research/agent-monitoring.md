# AI Agent Monitoring & Observability — Research (Lipiec 2026)

## Stan rynku (2026)

6 platform produkcyjnych: LangSmith, Langfuse, Arize Phoenix, Helicone, W&B Weave, Braintrust.

| Platform | Open Source | Best For | Cena |
|----------|-------------|----------|------|
| **Langfuse** | ✅ (MIT) | LLM traces, self-hosted | Free (self-host) / Paid (cloud) |
| **LangSmith** | ❌ | Unified platform (obs + evals + prompts) | Paid |
| **Arize Phoenix** | ✅ | Evals, span-level tracing | Free (OS) / Paid |
| **Helicone** | ✅ | Gateway-level, cost tracking | Free tier / Paid |
| **W&B Weave** | ❌ | Experiment tracking + LLM monitoring | Free tier / Paid |
| **Braintrust** | ✅ | Evals, datasets, logging | Free tier / Paid |

## Hermes + Monitoring

Hermes ma wbudowane:
- `hermes insights` — token usage, costs, tool patterns
- `--usage-file PATH` — JSON usage report (one-shot mode)
- Session store (SQLite + FTS5)

**Brakuje**: tracingu per-tool-call, latency breakdown, error rate tracking.

## Rekomendacja

### POV #11: Langfuse + Hermes
- Open-source, self-hosted (Docker — niedostępne na tej VM)
- Można użyć cloud tier (free)
- Tracing: każdy tool call → span w Langfuse
- **Impact: 7/10, Effort: 5/10**
