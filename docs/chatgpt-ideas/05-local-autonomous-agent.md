# 05 · Self-hosted general agent (OpenManus alternative)

**Status vs Hermes:** mostly done. Hermes Agent is the self-hosted general-purpose agent: Kanban workers, Claude Code for coding, a computer-use skill, browser automation POVs, and the CrewAI stack (stopped since 2026-10-06). What remains is an optional evaluation of browser/computer-use agents for web tasks Hermes handles badly.
**Priority:** P4

## Goal and context
In August 2025 Filip looked for an OpenManus-like agent he could deploy locally (candidates included OpenHands, browser-use and Agent-Zero). Since then he built Hermes, so the original need is covered.

Source: fjkazmierczak account, *Local open-manus alternatives* (2025-08-11).

## Architecture
No new platform. If a gap appears, add a **tool** to Hermes rather than a second agent:
- `browser-use` or Playwright MCP as a Hermes tool for multi-step web tasks
- an OpenHands-style sandboxed runtime only if Claude Code plus the coder profile cannot do the job

## Implementation plan
1. Collect 10 real web tasks Hermes failed at (from Kanban blocked tasks or Filip's requests).
2. Run them with the current Hermes tools, then with browser-use plus a cloud model. Compare success rate and cost.
3. Adopt the winner as a tool only if success improves by at least 30% at similar cost.

## Deployment plan
Run as a container on the dev VM, with the sandbox network restricted. No new always-on service.

## Configuration
The model provider goes through the existing Hermes config. Local models only via llama.cpp `llama-server` (OpenAI-compatible); never local Ollama.

## Cost / hardware
A headless Chromium needs about 1 GB RAM. LLM cost follows the existing quotas.

## Open questions
Are there concrete tasks Hermes can't do today? If not, close this idea.
