# 29 · Demo and presentation agent after a PR

**Status vs Hermes:** new. Building blocks exist: skills `powerpoint`, `manim-video`, `claude-design`; Hermes TTS (Piper / ElevenLabs).
**Priority:** P3

## Goal and context
Filip's agents already write, test and push code and run pipelines. He wants the last step too: when a feature PR is ready, the agent prepares him to present it to the team. That means a demo script, speaker notes, and a PowerPoint deck only when the agent decides one is needed. He has an O365 subscription and works in VS Code with Copilot.

Source: kazmierczakfilipjan, *Automating Demo and Presentation* (2026-08-11). It asked for the full agent spec: prompt, input/output JSON schema, folder layout, decision rule and the pipeline stage where it runs.

## Architecture
```
PR ready (CI green) ─► presentation-agent (separate stage, read-only on code)
  input  : PR title/body, diff stats, linked work item, test results, screenshots/recordings from CI
  step 1 : manifest.json  {audience, change_type, needs_deck: bool + reason, demo_steps[], risks[], talking_points[]}
           needs_deck = user-visible change OR architecture change OR > N files across components
  step 2 : render from the manifest (no free-form generation):
           demo.md (click-by-click script), notes.md (2–5 min speech), deck.pptx (python-pptx from a team template)
  output : attached to the PR as artifacts + a PR comment with links
```

## Implementation plan
1. Define the manifest JSON schema and the decision rule. Write 5 example manifests from past PRs by hand.
2. Renderers: python-pptx with the company template, markdown for demo and notes. No LLM in rendering.
3. The agent prompt fills only the manifest. Validate it against the schema and retry once on failure.
4. Hook: an Azure DevOps / GitHub Actions stage after tests pass, or a Hermes Kanban task that is created when a PR gets the `ready` label.
5. Optional: record the demo automatically with Playwright for web features and attach the video.

## Deployment plan
A skill plus a small CLI in hermes-enhancements. At work, the stage runs in the work CI with the company's model access.

## Configuration
Template .pptx path, audience presets (team, management), max slide count, language (PL/EN).

## Cost / hardware
One model call per PR (a few thousand tokens). Free otherwise.

## Open questions
- Is a company template available, and may PR content leave the work tenant (for the model call)?
- Does Filip want speaker notes in Polish or English?
