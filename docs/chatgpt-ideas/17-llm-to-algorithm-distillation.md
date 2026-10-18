# 17 · Turning recurring LLM work into deterministic code (cost boundary)

**Status vs Hermes:** partly exists. Pieces already in place:
- skill `devops/hermes-scripted-cron`: no-LLM cron jobs for deterministic work
- `teach-procedures`: turns observed procedures into skills
- chore-voice: a state machine instead of free chat
- `llm_triage/classify.py`: rules first

There is no general method and no measurement of which agent work to replace.

**Priority:** P1

## Goal and context
Filip's thesis: there is a profitability boundary between work an LLM agent should do and work that should be rewritten as an algorithm. Most repeated AI work should become code, and that investment pays off in the long run within well-defined limits. He asked whether a mathematical result supports replacing any intelligence with a finite algorithm, then had a cost formula drafted with all its components.

Source: fjkazmierczak account.
- *Dowód zastępowania inteligencji* (2026-09-30)
- the follow-up in *Ollama Clef classifier overview* (2026-10-07)

## Architecture
Write code for a task when the expected LLM cost over the horizon exceeds the cost of building and maintaining code plus the cost of the code's errors:
```
N·(c_llm + p_llm_err·c_err)  >  C_build + N·c_run + p_code_err·N·c_err + C_maint(T)
N = runs over horizon T, c_llm = tokens×price + latency cost, C_build ≈ agent/dev hours,
p_* = failure rates (measured), C_maint = drift (APIs change, inputs vary)
```
Measurement loop on Hermes:
```
session logs / cron usage_audit / kanban runs → cluster recurring task signatures (same tool sequence)
   → per cluster: frequency, tokens, failure rate → score by formula
   → top candidates → Kanban "distill" task: write script + tests, switch cron to no_agent / plugin tool
   → keep LLM as fallback when script exits with "unknown input"
```
This directly targets the earlier token burn (the autonomy planner used about 1.26B tokens).

## Implementation plan
1. `distill_report.py`: parse `cron/usage_audit.jsonl`, the Kanban DB and session tool-call sequences, and rank recurring patterns by tokens per week.
2. A weekly scripted cron writes the report to `autonomy/distill.md`. Filip picks 1–2 candidates.
3. Template: a "distilled tool" (script + tests + `fallback_to_llm` exit code) and its registration as a no-agent cron or plugin tool.
4. Track savings: tokens per week before and after, in the trace dashboard (`trace-dashboard/`).

## Deployment plan
Report script on the dev VM (Kanban and logs live there). Distilled tools ship through normal PRs.

## Configuration
Horizon T (default 90 days), prices from `budget.json` `prices_per_mtok`, minimum frequency threshold.

## Cost / hardware
Negligible. The report itself uses no LLM.

## Open questions
Which logs are the best source of tool-call sequences: `state.db` sessions, or Honcho telemetry?
