# 38 · Eye-tracking control on a Windows PC (Vision Pro-style "look to select")

**Status vs Hermes:** new.
**Priority:** P5

## Goal and context
Filip wanted Apple Vision Pro's "look at a window or menu item to select it" on his Windows PC, using a camera.

Source: kazmierczakfilipjan, *Eye tracking on Windows* (2025-11-25).

## Architecture
A plain webcam is too imprecise for menu-level selection (about 2–5° error, which is several centimetres on screen). Options:
```
A (works today): Tobii Eye Tracker 5 (IR, ~€250) → Windows Eye Control / Tobii Experience
                 → gaze focuses windows; click by dwell, key or voice
B (DIY, coarse) : webcam → MediaPipe face mesh + iris → gaze region (screen thirds)
                 → AutoHotkey: focus the window in that region; click stays on mouse/keyboard
```
Use B only as an experiment for window focus. Use A for real use.

## Implementation plan
1. Try B in an evening with a Python script (MediaPipe) plus AutoHotkey for window focus. Measure accuracy.
2. If useful but too coarse, buy a Tobii 5 and combine gaze focus with a voice command ("click") through the HA/Hermes voice pipeline ([22](22-ambient-voice-companion.md)).

## Deployment plan
Local install on the Windows PC.

## Configuration
Calibration profile, dwell time, hotkeys.

## Cost / hardware
B is free. A is ~€250.

## Open questions
- Is this for comfort, or for accessibility? Accessibility would justify the Tobii hardware right away.
