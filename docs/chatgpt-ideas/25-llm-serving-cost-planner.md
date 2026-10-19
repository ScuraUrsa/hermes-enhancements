# 25 · LLM serving and cost planner (self-host vs API, sizing calculator)

**Status vs Hermes:** partly exists. Ollama Cloud is the main provider (keys via `ollama_keys.py`, quota-governor, skill `ollama-model-selection`); local Qwen3.5-4B via llama.cpp on the laptop (`tasks/local-qwen-rollout.md`); `cheap_route` llama.cpp router; `vbench`/`hbench` and `trace-dashboard` for cost per provider. Missing: a sizing calculator, a self-host vs API break-even model, and any cloud GPU VM plan.
**Priority:** P3

## Goal and context
From 2026-02 to 2026-06 Filip ran large open-weight models (Qwen2.5/3.5 32B, coder models, later DeepSeek V4 / GLM-5 questions) on Azure GPU VMs and wanted to know:
- which VM fits which model, at "slow but cheap" (3–10 tok/s) vs "conversational" speed;
- how to calculate the minimum VM mathematically (weights + KV cache + throughput), and when to scale up vs out;
- reserved vs spot vs on-demand, and when an API (or Ollama Cloud) is cheaper than self-hosting;
- which models are best for coding vs architecture, and which fit a laptop;
- open-source image models similar to Nano Banana.

Source: kazmierczakfilipjan.
- *Best AI Coding Models* (2026-01-21), *Open-source LLM for Coding* (2026-02-02), *VM Image vs Terraform* (2026-02-03), *Tanie VM na chmurach* (2026-02-10), *Model vs System myślenie* (2026-02-20)
- *Open-source LLM w Ollama* (2026-03-07), *Zarządzanie modelami Ollama* (2026-03-09), *Ollama Docker Setup*, *VM Resource Prediction for LLM* (2026-03-13), *LiteLLM as Proxy* (2026-03-16), *Azure VM for LLM*, *Azure compute capacity analysis* (2026-03-19), *LLMs for Local Coding* (2026-03-26)
- *LLM Cost Optimization* (2026-04-14), *Azure VM Setup for GLM* (2026-04-25), *Deploying Qwen 3 Laptop* (2026-05-22, Ollama vs LM Studio vs llama.cpp), *DeepSeek V4 Pro VM* (2026-06-02), *LLM Hosting Comparison* (2026-06-10, Foundry vs spot VMs)
- *Modele open-source podobne do Nano Banana* (2025-12-19)

## Architecture
Filip's rule: **local = llama.cpp only**; Ollama is used only for its cloud models.
```
llm-plan (CLI, pure Python, no LLM)
  input : model card (params, active params for MoE, layers, kv heads, head dim), quant (Q4_K_M/Q8/FP8),
          context, concurrency, target tok/s, monthly token volume
  output: VRAM/RAM need = weights + KV cache(ctx × concurrency) + overhead
          candidate SKUs (Azure/AWS/GCP price table, spot/reserved), est. tok/s from memory bandwidth
          break-even vs API price per 1M tokens (Ollama Cloud, Anthropic, OpenRouter)
serving (if self-hosting ever wins): llama-server (llama.cpp) per model on a spot VM,
          behind the existing router (cheap_route / Hermes provider), scale-to-zero by queue length
```
Decode speed is bounded by memory bandwidth ÷ bytes read per token. That gives a quick tok/s estimate without benchmarks.

## Implementation plan
1. Write `llm-plan` with a YAML price table and model cards for the models Filip asked about. Unit-test the KV-cache formula against known llama.cpp numbers.
2. Add a "break-even" report: for the measured Hermes monthly token volume (from `trace-dashboard`), compare Ollama Cloud Pro vs a spot H100 vs an owned used-GPU rig ([41](41-used-gpu-llm-rig.md)).
3. Add laptop/homelab presets (GTX 1650 Ti 4 GB, 32 GB RAM) so the tool answers "what fits locally?".
4. Only if a self-host case wins: a Terraform module for one spot GPU VM with llama-server, started on demand by the Kanban dispatcher and stopped when idle.

## Deployment plan
The CLI lives in hermes-enhancements as `llm-plan/`, with a Hermes skill wrapper. No infrastructure unless step 4 is approved.

## Configuration
Price table (update monthly by a scripted cron that only fetches public price APIs), model cards, current API prices.

## Cost / hardware
The tool is free. A spot H100 runs at roughly 20–40 % of on-demand, but it can be evicted. That is fine for batch Kanban work, not for chat.

## Open questions
- Is there any workload where self-hosting beats Ollama Cloud for Filip today? Privacy-only workloads may be the one case.
- Should image generation (open Nano-Banana-like models such as Qwen-Image or FLUX Kontext) be part of this, or a separate idea?
