# 05 · Self-hosted general agent (OpenManus alternative)

**Status vs Hermes:** mostly done. Hermes Agent is the self-hosted general-purpose agent: Kanban workers, Claude Code for coding, a computer-use skill, browser automation POVs, and the CrewAI stack (stopped since 2026-10-06). What remains is an optional evaluation of browser/computer-use agents for web tasks Hermes handles badly.
**Priority:** P4

## Goal and context
In August 2025 Filip looked for an OpenManus-like agent he could deploy locally (candidates included OpenHands, browser-use and Agent-Zero). Since then he built Hermes, so the original need is covered.

Source: fjkazmierczak account, *Local open-manus alternatives* (2025-08-11).

Also from the **kazmierczakfilipjan** account, a long run of agent-stack threads from 2026-02 to 2026-06:
- *Open-source LLM for Coding* (2026-02-02), *CrewAI Multiple Agents Setup*, *Integrating OpenClaw with Ollama* (2026-03-03), *Open WebUI CrewAI Setup* (2026-03-04), *AI Stack Integration Guide*, *OpenClaw vs CrewAI* (2026-03-05), *Darmowe opcje deploymentu* (2026-02-11, CrewAI/LangGraph licensing)
- *OpenClaw Installer Help* (2026-04-02), *Security of OpenClaw on Linux* (2026-04-09), *GitOps OpenClaw Deployment* (2026-04-07)
- *Hermes i Qwen3.5 4B* (2026-06-11), *Tanie hostowanie Hermesa* (2026-08-04), *Hermes Profile Decision Tree*, *Cheapest Kanban Orchestrator Models*, *Markdown vs Database Memory* (2026-05-29), *Self-hosting Honcho Check* (2026-05-25)

These show the path Filip took: CrewAI + OpenClaw + Ollama + Open WebUI on Azure GPU VMs, then a move to Hermes. That move is what makes this idea "done".

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

## Additions from the kazmierczakfilipjan account
- **Hermes replaced the CrewAI/OpenClaw stack.** Do not revive it. The remaining good ideas from those threads are tracked elsewhere: a sandboxed worker for risky execution ([27](27-agent-sandboxes.md)), Open WebUI as a front-end ([26](26-open-webui-front-end.md)) and model serving ([25](25-llm-serving-cost-planner.md)).
- **Profile split rule** (from *Hermes Profile Decision Tree*): create a new profile only when the best tools, memory, model or evaluation criteria change. A new topic alone is not a reason. This matches the current profile set (coder, researcher, writer, maintainer, reviewer, architect).
- **Memory rule** (from *Markdown vs Database Memory*): curated, stable facts go to markdown memory files. Fast-changing, searchable facts go to Honcho. That is already how Hermes works.

## Open questions
Are there concrete tasks Hermes can't do today? If not, close this idea.
