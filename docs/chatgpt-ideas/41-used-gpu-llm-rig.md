# 41 · Budget multi-GPU LLM rig from used or repaired cards

**Status vs Hermes:** new. Local inference today is Qwen3.5-4B on the laptop's GTX 1650 Ti via llama.cpp; no GPU server.
**Priority:** P3

## Goal and context
Filip wants to buy damaged or used GPUs, repair them, and build a homelab rig for local LLMs. He asked:
- what else is needed besides the cards, and what the best multi-GPU layout is;
- whether cheap old cards (GTX 1050 2 GB for 70 PLN) help at all;
- how to repair an MSI GTX 1080 Ti that shows artefacts or isn't detected, and what it means when a card crashes within a second of a stress test;
- whether a cluster of weaker cards can replace one big card, judged by **energy cost per million tokens** rather than raw tok/s.

Source: kazmierczakfilipjan, *Naprawa MSI GTX 1080 Ti* (2026-04-03), *Optymalny homelab dla LLM* (2026-07-07), *AI na klastrze GPU* (2026-07-30).

## Architecture
```
open-frame mining-style rig or used workstation (EPYC/Threadripper/Xeon W for PCIe lanes; or consumer board + x4 risers)
  GPUs: VRAM per € first: RTX 3090 24 GB (used), Tesla P40 24 GB (cheap, slow FP16), 3060 12 GB
        cards < 8 GB VRAM: repair practice only, not for inference
  PSU: ATX 1200–1600 W 80+ Platinum (or server PSUs + breakout boards), power-limit cards to ~70 %
  inference: llama.cpp (llama-server) with --split-mode layer across cards; RPC backend for a second box
  monitoring: nvidia exporter → observability stack (20); smart plug for wall-power metering
  scheduling: Hermes wakes the rig (WoL) for batch Kanban jobs, sleeps it when idle (19)
```
Layer split needs little PCIe bandwidth, so x4 risers are fine for llama.cpp. Tensor parallelism (vLLM) needs x8/x16 and matched cards.

## Implementation plan
1. Decide the target model size first (e.g. a 70B Q4 needs ~40–48 GB VRAM → 2× 24 GB). Use the calculator from [25](25-llm-serving-cost-planner.md).
2. Repair bench: thermal camera or thermal pads check, multimeter, a spare test PC with an open PCIe slot. Write a "card intake" checklist (visual, VRM short check, POST, OCCT VRAM test, power-limited burn-in).
3. Build with two cards. Benchmark tok/s and wall power with llama-bench. Compute € per 1M tokens including electricity (PLN/kWh).
4. Compare with Ollama Cloud cost for the same monthly volume. Add cards only if the rig wins.

## Deployment plan
Bare-metal Linux (or a Proxmox node with GPU passthrough). llama.cpp built by a WOBI role with CUDA, model files on the hot disk.

## Configuration
Power limits per card, model list, idle shutdown timer.

## Cost / hardware
Used 3090 ~2,500–3,000 PLN each; P40 ~800–1,000 PLN; platform + PSU + frame ~1,500–3,000 PLN. Electricity is the main running cost: a 2-card rig at ~600 W costs about 0.6 kWh per hour of generation.

## Open questions
- Is the motivation cost, privacy, or learning hardware repair? If cost, Ollama Cloud probably wins at Hermes' current volume.
- Noise and heat: where in the flat can a 600 W+ rig run?
