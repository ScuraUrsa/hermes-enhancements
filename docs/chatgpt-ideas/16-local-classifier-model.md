# 16 · Small local classifier model for routing and labelling (Cloudflare Clef)

**Status vs Hermes:** partly exists. `cheap-route` uses a small llama.cpp model (Qwen3.5-4B / Gemma) to route questions, with an eval set of 83 questions. WOBI `crewai/llm_triage` has a rule-based classifier and router, and `vbench` picks models per video type. Nobody has evaluated a dedicated classifier model like Clef.
**Priority:** P2

## Goal and context
Cloudflare's Clef (27B) and Clef Flash (9B) were announced as Ollama models. They return categories, yes/no answers or scores for text and images. Filip asked about use cases: ticket and bug labelling, routing, image checks. He also asked whether they can identify people from photos (answer: no, and that shouldn't be built).

Source: fjkazmierczak account, *Ollama Clef classifier overview* (2026-10-07).

Also from the **kazmierczakfilipjan** account: *Model lokalny do browser-use* (2026-06-23, the smallest local model that is enough for repeated clicks on known pages and desktop apps). That use case is planned in [23](23-computer-use-automation.md).

## Architecture
Filip's rule is local models via **llama.cpp only, never local Ollama**:
```
input (Kanban task text, inbox item, HA camera/vacuum obstacle image)
   → llama-server (Clef Flash GGUF, --mmproj for images, JSON-schema grammar for output)
   → {label, score} → deterministic router (cheap-route rules / Kanban assignee / HA automation)
```
Planned uses inside Hermes:
- **Kanban triage:** assign a profile and priority to new tasks, and flag busywork (P3 issue #12 in HERMES_MAP).
- **cheap-route:** compare against the current Qwen3.5-4B evaluator on the existing 83-question set.
- **Vacuum obstacles:** "socks / toys / cable" labels for [06](06-robot-vacuum-valetudo.md).

If Clef is only distributed through the Ollama registry, either convert it to GGUF (when the license allows and llama.cpp supports the architecture) or use it through **Ollama Cloud**, which the rules allow. Otherwise keep the current Qwen/Gemma setup.

## Implementation plan
1. Check the license, the published weights (HF), the base architecture, and whether llama.cpp supports it and a GGUF exists.
2. Add `bench_route.py --model clef-flash` to the cheap-route evaluator. Acceptance: 0 false `free_web` and ≥ 90% agreement, the same bar as today.
3. If it wins: swap the model in cheap-route's `serve.ps1`/llama-server config. Add a Kanban triage hook that only suggests and logs, and a human applies.

## Deployment plan
llama-server on the Windows PC (`D:\hermes\_llamacpp`, which already exists) or on a future GPU box. The prod VM (8 GB RAM, no GPU) is too small for 9B at useful speed.

## Configuration
Model path, `--ctx-size 4096`, a JSON grammar per task, label sets in `cheap-route/evaluator/`.

## Cost / hardware
- A 9B Q4 GGUF is about 5.5 GB RAM.
- On the GTX 1650 Ti (4 GB VRAM) it runs with partial offload, at a few tokens/s. Classification outputs are short, so that is acceptable.
- 27B needs 16 GB+ VRAM.

## Open questions
- Is a GGUF available, or is the model Ollama-only?
- Is a 9B classifier actually better than the 4B general model plus the rules already in place?
