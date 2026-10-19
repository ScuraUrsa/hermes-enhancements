# 23 · Computer-use automation: record once with AI, replay as a script

**Status vs Hermes:** partly exists. Skill `computer-use`, WOBI role `desktop` (Xvfb, noVNC, xdotool), skill `teach-procedures` + `hermes-gui-automation/teach` (record a procedure, replay it), browser-use web UI Dockerfile in WOBI `docker/`. Missing: compiling a recorded run into a no-LLM script with AI repair only on failure, and the app-watcher mode.
**Priority:** P2

## Goal and context
Filip wants agents to use a PC the way a person does (browser, Windows and Linux desktop apps, Android), but cheaply:
- The AI does a task once, then turns it into a deterministic script (AutoIt / Playwright). The AI is called again only when the script fails or the UI changes.
- Hermes watches a logged-in app (refreshing every second or so), notices changes and tells Filip what to click.
- Pick the smallest local model that can handle repeated clicks on known pages.

Source: kazmierczakfilipjan.
- *Copilot browser-use integration* (2026-04-03), *Ollama Models for Browser Automation* (2026-04-09)
- *AI Agents for Automation* and *Enhance Conversation Output* (2026-04-14, AutoIt vs computer-use agents; architect → spec compiler → workers)
- *Model lokalny do browser-use* (2026-06-23)
- *Computer-use-linux vs Claude Code* (2026-06-24)
- *Agent Hermes monitorowanie aplikacji* (2026-07-08)

## Architecture
```
task ─► recorder run (vision agent: browser-use for web, Claude computer use / windows-use for desktop)
          │ every action logged as a step: selector/UIA id, fallback coords, screenshot hash
          ▼
        compile → script (Playwright for web, AutoIt/pywinauto for Windows, xdotool for Linux, adb for Android)
          ▼
        replay (no LLM) ──ok──► done
          │ fail / screenshot diff > threshold
          ▼
        repair run (vision agent on the failing step only) → patch script → PR to the scripts repo
watcher: poll app (DOM or screenshot) → diff → small local model (llama.cpp VLM) classifies the change
         → notify Filip ("click X") via Matrix / phone
```

## Implementation plan
1. Pick one real repetitive web task as the pilot (a portal Filip clicks through weekly).
2. Run browser-use with a strong cloud model to record it. Save the step log.
3. Write a compiler from the step log to a Playwright script. Run it on a Hermes cron.
4. On failure, call the agent with the step, the old screenshot and the new one, then patch and open a PR.
5. Add the "watcher" mode: Playwright polls a logged-in page and diffs the relevant region. A small local VLM via llama.cpp (Qwen2.5-VL 3B/7B class) decides if it matters. Notify via Matrix.
6. Windows desktop: the same flow with pywinauto (UI Automation tree) first. Use AutoIt only where UIA has nothing.

## Deployment plan
The scripts repo lives next to Hermes skills. Playwright runs headless on the VM. Windows tasks run on the Windows PC through an SSH-triggered runner.

## Configuration
Per-task: target URL/app, credentials from Bitwarden (never in the script), schedule, failure budget before human escalation.

## Cost / hardware
Recording uses cloud model tokens once per task. Replay is free. A local VLM for the watcher needs ~6–8 GB VRAM or runs slowly on CPU.

## Open questions
- Which concrete tasks are worth it? Without a list, this stays a demo.
- Terms of service of the target sites: some forbid automation.
