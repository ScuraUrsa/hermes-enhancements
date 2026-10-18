# 20 · Observability for the homelab and Hermes (metrics, logs, traces)

**Status vs Hermes:** partly exists. Pieces in place:
- host-daemon health monitor design (hermes-workspace)
- Langfuse POV (`POV/11-langfuse-monitoring`), `research/agent-monitoring.md`
- `llm_triage/telemetry.py` (JSONL)
- `trace-dashboard/` (prompt → sessions → commits, tokens and cost)
- WOBI `roles/security_watch`

There is no metrics or log stack (Prometheus/Grafana/Loki) and no alerting to Filip.

**Priority:** P2

## Goal and context
Filip asked about the difference between monitoring and observability. Monitoring covers known failure modes with metrics and alerts. Observability lets you ask new questions of the system through metrics, logs and traces with correlated context.

Source: fjkazmierczak account, *Monitoring vs Observability* (2026-08-08).

## Architecture
A lightweight stack sized for an 8 GB VM:
```
node_exporter + cAdvisor + (Windows) windows_exporter
   → VictoriaMetrics single-node (or Prometheus)  ← lower RAM than Prometheus
journald/docker logs → Grafana Alloy (or Vector) → Loki (single binary, filesystem, 14-day retention)
Hermes/LLM traces → existing trace-dashboard (+ OTLP export later)
Grafana (dashboards) → alert rules → Matrix room / phone (Matrix server already live) 
Key alerts: disk > 85% (it reached 92% before), gateway down, cron job failing N times,
            Ollama 429 rate, self-budget exhausted, backup age > 26 h, VM uptime reset.
```

## Implementation plan
1. WOBI role `observability` with a compose stack (VictoriaMetrics, Loki, Alloy, Grafana) and memory limits (about 600 MB in total).
2. Dashboards: VM host, Docker containers, Hermes (gateway, cron, Kanban counts via a small exporter script), costs from `budget.json`.
3. Alerts to Matrix via Grafana contact point (webhook → bridge), with an "alert rule → runbook link" convention.
4. Later: OTLP traces from Hermes tool calls into Tempo, only if trace-dashboard is not enough.

## Deployment plan
Apply on dev first, then prod through `pull.sh`. Grafana stays bound to localhost/Tailscale only.

## Configuration
Retention (metrics 30 d, logs 14 d), scrape targets, the alert routing table, Grafana admin password in Bitwarden.

## Cost / hardware
Free software. About 600 MB–1 GB RAM and 2–5 GB disk. Check the free disk space on prod first.

## Open questions
- Host it on prod (watching itself) or on dev (watching prod)? A dev box watching prod survives prod outages.
- Is Matrix the agreed alert channel?
