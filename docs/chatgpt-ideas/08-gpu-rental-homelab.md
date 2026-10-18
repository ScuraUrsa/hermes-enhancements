# 08 · Renting out homelab GPU hardware

**Status vs Hermes:** new.
**Priority:** P4

## Goal and context
Filip asked whether it pays to buy hardware just to rent it out online, given power costs and hardware prices. He also asked which platforms take home hardware: SaladCloud, Vast.ai, TensorDock, Clore.ai, io.net and similar. The chat estimated earnings for an RTX 4090 in Poland.

Source: fjkazmierczak account, *Hardware rental profitability* (2025-08-14).

## Architecture
```
Linux host (bare metal, not WSL/VirtualBox) + GPU → provider agent (Vast.ai host daemon / Salad node / TensorDock host)
                                                   → Prometheus node + nvidia exporter → profit dashboard
```
This does not fit the Hermes host. Hermes runs in a VirtualBox VM on Filip's Windows PC, and providers need a dedicated Linux host with GPU passthrough and stable uptime.

## Implementation plan (decision first, build later)
1. Build a profitability model: (market $/h × utilisation × (1 − fee)) − (W × hours × PLN/kWh) − depreciation. Fill it with live marketplace prices before any purchase.
2. Zero-capex test: run SaladCloud on the existing PC GPU while idle (Windows client) for 2 weeks and measure real PLN/day.
3. Buy dedicated hardware only if the test and the model show more than 25% annual ROI after power.

## Deployment plan
For a dedicated box: Ubuntu Server, the provider's install script, a UPS, and a separate VLAN (it runs untrusted workloads).

## Configuration
Power price (PLN/kWh, including distribution charges), min price per hour, the hours the machine is available.

## Cost / hardware
An RTX 4090 box costs roughly 10–14k PLN. It draws about 450 W under load, and at ~1.1 PLN/kWh that is about 12 PLN/day of power at 100% use. Marketplace prices fell through 2025–26, so payback is often more than 2 years. Treat this as low priority.

## Open questions
- Is the real goal income, or subsidising a GPU that Filip also wants for local LLMs (llama.cpp) and robotics ([07](07-open-source-robot.md))? If it's the latter, the dual use changes the math.
- Tax treatment of the income in Poland.
