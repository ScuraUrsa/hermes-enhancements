# 40 · GitHub Copilot and Claude subscription as Hermes coding back ends

**Status vs Hermes:** partly exists. Claude Code runs through `cc_run.py` on Filip's subscription (WOBI role `claude_code`); Copilot profiles `copilot-pro` / `copilot-archive` exist and Copilot appears in `bench/hbench`, but the Copilot CLI is not installed on the VM. Zed's headless agent, `codex` and `opencode` skills exist.
**Priority:** P3

## Goal and context
Filip has a GitHub Copilot subscription (work and private) and a Claude Pro subscription. He wanted to:
- let agents call Copilot (Copilot CLI with a chosen model, autopilot / allow-all, non-interactive), instead of using Copilot only in VS Code;
- wrap Copilot as if it were an Ollama model so other agents can use it (and check whether that breaks GitHub's terms);
- reuse Claude Code skills in Copilot, and make Copilot write CrewAI-consistent agents from shared instructions;
- understand reasoning levels, YOLO mode, premium-request limits, and a Hermes error where a Copilot model name worked in the CLI but not in Hermes;
- know whether Hermes should use an Anthropic API key or Workload Identity Federation, and whether a Claude Pro subscription works with API keys (it does not; API use is billed separately).

Source: kazmierczakfilipjan.
- *GitHub Copilot vs VS Code*, *Ollama Models for Browser Automation* (2026-04-09), *Using Copilot CLI with Ollama* (2026-04-14), *Copilot browser-use integration* (2026-04-03), *VSCode Copilot Shortcuts* (2026-04-08)
- *Claude Code in Copilot*, *GitHub Copilot and CrewAI Integration*, *GPT-5.4 vs Claude 4.6* (2026-05-06), *Copilot Premium Usage Check* (2026-05-15)
- *Model reasoning level change* (2026-05-28), *Ustawienie YOLO mode Copilot* (2026-05-29), *Copilot CLI flags setup* (2026-06-01)
- *Zed Editor błąd GUI*, *ZED Agent Operations* (2026-03-05), *Zed LiteLLM Configuration* (2026-03-21), *Zed System Prompt Location* (2026-04-07)
- *Workload identity federation vs API key* (2026-10-04), *Dodawanie czatu do projektu* (2026-10-05)

## Architecture
```
Kanban coding task → dispatcher picks a back end by budget and task type
   ├─ Claude Code  (cc_run.py, subscription)               default for repo work
   ├─ Copilot CLI  (copilot -p … --model … --allow-all --silent, in the worktree)  when Claude quota is low
   └─ cheap/local  (cheap_route, Ollama Cloud)              trivial edits, summaries
shared instructions: AGENTS.md + ~/.agents/skills (WOBI coding_agents) — one source, linked into
                     .github/copilot-instructions.md and .claude/ by a sync script
```
Calling the official Copilot CLI from a script is supported. Wrapping Copilot as a fake Ollama/OpenAI endpoint for other tools is a grey zone in GitHub's terms, so don't build it.
Auth: Hermes keeps using the Claude subscription through the official CLI. WIF only matters if Hermes ever calls the Anthropic API from a cloud workload.

## Implementation plan
1. Install Copilot CLI via the `coding_agents` role (pinned version, 7-day cooldown) and log in with the private account.
2. Add a `copilot` runner next to `cc_run.py` with the same contract (task id, worktree, log line in `claude_runs.jsonl`-style file, exit codes for quota).
3. Teach the quota governor to fall back to Copilot when Claude returns quota exit 75.
4. Skills portability: a sync script that renders `~/.agents/skills/*/SKILL.md` into Copilot's instruction files. Keep one source.
5. Fix the Hermes Copilot provider model-name mapping (the "model not supported" error) and add a test.

## Deployment plan
WOBI role change and a Hermes script; feature flag in `features/registry.yaml`.

## Configuration
Copilot model per task type, premium-request budget per month, fallback order.

## Cost / hardware
Uses existing subscriptions. Copilot premium requests are capped per month; track them in the quota file.

## Open questions
- May the private Copilot seat be used by an unattended agent, at the volume Hermes would use?
- Should the work Copilot ever be connected? Probably not; keep work and private agents apart.
