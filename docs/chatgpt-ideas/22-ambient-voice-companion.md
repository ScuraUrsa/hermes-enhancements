# 22 · Ambient voice companion for Hermes ("Hey Hermes", proactive, with a face)

**Status vs Hermes:** partly exists. Home Assistant with Polish Whisper STT + Piper TTS and the `openai_compatible` integration pointed at Hermes is live since 2026-10-09 (phone paired); skill `hermes-voice-assistant`, design `tasks/voice-mobile-handoff.md`. Missing: a "Hey Hermes" wake word, proactive speech, the interjection gate and an avatar.
**Priority:** P3

## Goal and context
Filip wants Hermes to feel like a companion in the room, not a chat window:
- Wake word on the phone ("Hey Hermes"/"Hey Jarvis") that opens a direct Hermes chat or runs a task.
- **Proactive speech.** Hermes speaks first when conditions are met ("Filip, that job should be done by now. Did you finish it?").
- It listens to the conversation and joins in **only when it can help**, not after every sentence and not only when called.
- A face: an animated avatar on the laptop screen (using the laptop camera, mic and speakers) or a small desk robot with a screen face.

Source:
- koalamis6: *Robotyka miniatury VR* (2026-07-21, the desk-robot, screen-face and "companion that listens" part), *Communicate with Hermes Android* (2026-08-26, review of the community `hermes-android` client for always-listening and proactive speech)
- kazmierczakfilipjan: *Custom AI Voice Assistant* (2026-05-22, phone wake word opening Open WebUI chat)

## Architecture
```
mic (phone / laptop / desk unit)
  → wake word (openWakeWord, custom "hej hermes" model)  ─┐
  → VAD + streaming STT (whisper.cpp, Polish)              │
                                                           ▼
             "should I speak?" gate  (small local model via llama.cpp, JSON yes/no + reason;
                                      cooldown, quiet hours, max N interjections/hour)
                                                           ▼
                         Hermes gateway (API) ── tools, memory, Kanban
                                                           ▼
             TTS (Piper, Polish voice; same as HA voice) → speaker
             avatar (Open-LLM-VTuber style Live2D face, emotion tag from the reply)
proactive triggers: Hermes cron/timeplane events → push to the companion → speak
```
Home Assistant Assist with the Polish voice pipeline already covers wake word → STT → TTS in the house. The companion reuses that pipeline rather than building a second one.

## Implementation plan
1. **Phone wake word, quick version.** HA Assist already routes to Hermes. Set the HA Companion app as the default Android assistant and enable on-device wake word (or train an openWakeWord "hej hermes" model for HA's Wyoming pipeline).
2. **Proactive messages.** Add a "say" action: Hermes cron/timeplane → HA `tts.speak` on a chosen speaker, or a phone notification with TTS. Gate it with quiet hours and a daily cap.
3. **Laptop avatar.** Run Open-LLM-VTuber (or similar) on the laptop, pointed at the Hermes gateway's OpenAI-compatible API and local whisper.cpp/Piper. Map an emotion tag in replies to avatar expressions.
4. **Ambient mode (experiment).** Rolling 2-minute transcript buffer, never stored by default. Every N seconds a llama.cpp classifier decides whether to interject. Measure false interruptions for a week before enabling it for others in the room.
5. **Desk robot (later).** Same software on a small screen-face robot (see [07](07-open-source-robot.md)).

## Deployment plan
HA config through the existing HA flow scripts. Avatar app on the laptop by hand. The interjection gate runs as a small service on the Hermes VM.

## Configuration
Wake-word model file, quiet hours, interjection cap, which rooms/devices may speak, a privacy switch (a mute button that is a real HA entity).

## Cost / hardware
Free software. Optional: a desk unit (ESP32-S3 box or Pi 5 with a round display), ~€50–120.

## Open questions
- Privacy: is always-on listening acceptable for other household members? It needs a visible indicator and consent.
- Does always-listening on Android drain the battery too much? The HA app may need to be limited to charging time.
