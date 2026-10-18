# 06 · Better robot vacuum, locally controlled (Valetudo + Home Assistant + "pusher" add-on)

**Status vs Hermes:** partly exists. Home Assistant runs on the prod VM, with local Polish Whisper/Piper and an `openai_compatible` integration to Hermes (WOBI `roles/home_assistant`). Nothing exists yet for vacuums, Valetudo or MQTT.
**Priority:** P2

## Goal and context
The household is not satisfied with the current Roborock S8. There are two pain points:
1. It can't clean under furniture or around toys and socks on the floor.
2. It needs daily emptying and cleaning, which nobody keeps up with.

Filip wants strong vacuuming and mopping with a self-emptying, self-washing dock. He wants a robot he can control and program himself (cloud-free), and maybe a 3D-printed "bulldozer" attachment, so that an AI agent could push items out of the way. The discussion compared Dreame X40/L40/X50/X60 Ultra models for Valetudo support, picker robots (Roborock with an arm), and how to write Valetudo extensions (TypeScript/Node).

Source: fjkazmierczak account, *Dobór robota sprzątającego* (2026-09-16).

## Architecture
```
Dreame (Valetudo-supported model, rooted)  ──MQTT──►  Mosquitto (VM)  ──► Home Assistant (VM)
        │ Valetudo REST/MQTT                                               │ automations: daily run when nobody home,
        │                                                                  │ dock status → phone notification
        └─ map + segments + "obstacle" images                              ▼
                                                                     Hermes (HA tool / voice):
                                                                     "posprzątaj kuchnię", "co blokuje robota?"
Phase 3 (experimental): obstacle photos → local VLM classifier (see 16) → list "socks under table"
                        → reminder to tidy up before scheduled run (cheaper than a robot arm)
```
An AI-driven pusher attachment is not recommended. It risks damage, voids the warranty, and needs reliable manipulation that consumer robots lack. The practical fix for clutter is a "tidy-up reminder" built from obstacle detection, plus raised furniture legs (≥ 10 cm clearance).

## Implementation plan
1. **Buy decision.** Check the current Valetudo supported-robots list and the Dustbuilder rooting method for the chosen model **before** buying. As of 2026-09 the X40/L40 Ultra had mature support; the X50 did not. Pick by: rootable with Valetudo + auto-empty + mop washing/drying + raised mop.
2. Root it and install Valetudo, following the official docs only.
3. Add Mosquitto to WOBI (a `mosquitto` role, auth enabled, localhost/Tailscale only). Use Valetudo MQTT autodiscovery in HA.
4. HA automations: scheduled clean on weekdays at 10:00 if presence = away, a notification when the bin or dirty-water tank is full, a weekly maintenance reminder.
5. Hermes: expose HA vacuum services through the existing HA integration. Add a skill `smart-home/vacuum` with Polish voice intents.
6. Optional: obstacle-image classification to produce a "tidy before clean" list.

## Deployment plan
Mosquitto and the HA config ship through a WOBI `iac/final` PR, applied on prod after a dev check. The robot joins the home Wi-Fi on an IoT VLAN if the router supports it.

## Configuration
MQTT user and password in Bitwarden (`MQTT_VALETUDO_PASSWORD`), Valetudo MQTT topic prefix, HA areas mapped to Valetudo segments.

## Cost / hardware
- Robot: roughly 3,000–5,500 PLN for an Ultra-class Dreame (2026 prices vary; check promotions).
- Rooting may need a USB adapter or a breakout PCB, roughly 50 PLN.
- Mosquitto adds about 20 MB RAM on the VM.
- Selling the S8 offsets part of the price.

## Open questions
- Which exact model and firmware? Rootability depends on the batch and firmware version.
- Is rooting (and losing the warranty) acceptable for a 4–5k PLN device?
- Does the VM host stay on 24/7? Schedules need HA up; the robot can also keep its own schedules in Valetudo.
