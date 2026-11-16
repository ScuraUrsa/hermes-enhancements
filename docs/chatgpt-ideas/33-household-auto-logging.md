# 33 · Low-friction household logging (drinks, shopping lists)

**Status vs Hermes:** partly exists. hermes-enhancements `home-inventory/`, Home Assistant on the VM, `link-inbox`. No drink tracking and no shopping-list integration.
**Priority:** P4

## Goal and context
- The assistant should know what and how much Filip drank without him saying it or opening an app. Is a camera enough, or is a smart scale needed?
- Turn a PDF (recipe or meal plan) into a shopping list in the Listonic app, possibly via Tasker.

Source: kazmierczakfilipjan, *Aplikacja Listonic na Androida* (2024-10-28), *Monitorowanie napojów AI* (2026-02-02).

## Architecture
```
drinks: smart coaster/scale (ESP32 + HX711 load cell, ESPHome) under the usual cup/bottle spot
        → HA sensor: weight drops = sip; a new container = a refill event
        + optional NFC tags on bottles/mugs (tap = "this is coffee/water") → HA
        → daily totals → Hermes (hydration and caffeine context for the day plan)
shopping: PDF → text (ocr-and-documents skill) → ingredient list (LLM, JSON) → merge with home-inventory
        → list in a self-hosted or API-friendly app (Bring!/Grocy/HA shopping list).
```
Listonic has no public API, so automating it needs Tasker/UI automation. A list app with an API or HA's own shopping list is more reliable.

## Implementation plan
1. Build one ESPHome scale coaster (~€15 in parts) and log events in HA for a week. Check whether a cup-on/cup-off pattern is recognisable.
2. Add NFC tags for drink type. Compute daily totals in HA templates and expose them to Hermes.
3. Shopping: a Hermes skill "PDF → list" writing to the HA shopping list (synced to the HA phone app). Use Listonic only if the family insists, via Tasker AutoInput.

## Deployment plan
ESPHome device config in git; HA config via the existing HA flow scripts.

## Configuration
Cup tare weights, drink types per tag, list target.

## Cost / hardware
ESP32 + HX711 + 1 kg load cell + 3D-printed coaster: ~€15. NFC tags ~€5.

## Open questions
- Is the camera route acceptable at all (privacy at the desk)? The scale avoids it.
- Who else uses the shopping list, and on which app?
