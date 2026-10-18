# 04 · Self-learning tool researcher (endless loop over a tool/skill list)

**Status vs Hermes:** partly exists. The 2026-08-29 autonomy run created 24 tool-research and 24 POC Kanban tasks (decision_log). Roadmap goal C3 says "monitor the ecosystem and save findings as skills". There are skills `technical-research-pov`, `spike` and `hermes-autonomy-loop`, and a sandbox dir `~/hermes-sandbox`. Missing: a persistent queue that adds the tools it discovers and has a clear "learned" criterion. The K8s POC series ended 2026-10-06 when its budget ran out.
**Priority:** P2

## Goal and context
An agent takes a list of tools or skills, researches each one on the internet, practises it in a test environment, and writes down what it learned. It runs forever until the list is empty, and adds new tools it discovers along the way. Filip asked which projects already exist (AutoGPT, BabyAGI, MetaGPT, Voyager-style skill libraries).

Source: fjkazmierczak account, *AI Self-Learning Framework* (2025-03-18).

## Architecture
```
learning_queue (SQLite: tool, status, depth, discovered_from, budget_used, skill_path)
   │ cron (scripted, no LLM) picks next item if self-budget allows
   ▼
Kanban task → researcher profile: docs → summary + quickstart
            → coder profile in sandbox (ephemeral container/kind/VM): run quickstart, write a test
   ▼
"learned" = smoke test passes in sandbox → skill saved (~/.hermes/skills/<cat>/<tool>/SKILL.md)
   │ discovered tools → queue with depth+1 (cap depth=2, relevance score ≥ threshold, Filip approves new categories)
```
The guards are the important part. The 2026-08/09 run burned about 1.26B tokens, so this loop needs hard caps:
- per-item and per-day budget (budget.py)
- max queue growth per day
- dedupe against existing skills

## Implementation plan
1. Add `learning_queue.py` (CLI: add/list/next/done/skip) and a seed list from Filip.
2. Scripted cron `learning-tick` (no LLM). It creates at most N Kanban tasks per day when quota mode is `coding` or `non_coding`.
3. Task template: research → sandbox POC → skill draft → reviewer profile checks the skill.
4. Discovery: the researcher returns `related_tools[]`. These go into the queue as `proposed` and only become `ready` after weekly approval through the user inbox.

## Deployment plan
Run on the dev VM `hermes-dev` (where Kanban runs). Sandboxes are Docker containers with no host mounts. Ship it as a PR to the autonomy scripts.

## Configuration
`autonomy/learning.yaml`: daily_max_tasks, max_depth, token budget per item, sandbox image and allowed categories.

## Cost / hardware
It only spends tokens inside the existing $4/day self budget. Sandboxes need 1–2 GB RAM each; prod has 8 GB, so run them one at a time.

## Open questions
- What is the seed list? (The DevOps tools from the 2026-08 series, or something else?)
- Should learned skills go to all profiles or only to the researcher and coder?
