---
name: coding-frameworks
description: Run a coding task through a full coding framework (Claude Code, GitHub Copilot CLI or Zed's agent) on a chosen model provider, and pick the combination from the hbench leaderboard.
version: 0.1.0
metadata:
  hermes:
    status: draft
    tags: [coding, kanban, claude-code, copilot, zed, ollama]
---

# Coding frameworks

DRAFT: describes the target behaviour in hermes-enhancements/bench/DESIGN.md §6. Until `code_run.py`
exists, Claude Code still goes through `~/.hermes/scripts/cc_run.py`.

## Choosing a combination

1. Read `~/.hermes/coding_routing.yaml` (generated from `hbench report --json`, approved by Filip).
   Pick the first entry for the task's category and difficulty whose quota is available
   (`~/.hermes/autonomy/quota/*.json`).
2. If the file doesn't exist yet: Claude Code + Anthropic for anything multi-file or risky; Claude Code
   + Ollama Cloud for small, well-specified changes; never send a repo containing committed secrets
   (`.env`, keys) to a cloud provider.

## Running it (always in the task's worktree, never in the main checkout)

Claude Code, Anthropic:

    claude -p "$PROMPT" --output-format stream-json --verbose --permission-mode auto --model sonnet

Claude Code, Ollama (local or cloud): same command, plus

    ANTHROPIC_BASE_URL=http://192.168.56.1:11434 ANTHROPIC_AUTH_TOKEN=ollama ANTHROPIC_API_KEY= \
    ANTHROPIC_DEFAULT_SONNET_MODEL=$M ANTHROPIC_DEFAULT_OPUS_MODEL=$M ANTHROPIC_DEFAULT_HAIKU_MODEL=$M \
    CLAUDE_CODE_SUBAGENT_MODEL=$M claude -p "$PROMPT" --model $M ...

GitHub Copilot CLI (GitHub-hosted model, separate quota):

    copilot -p "$PROMPT" --allow-all-tools --model $M

GitHub Copilot CLI on Ollama: `COPILOT_PROVIDER_BASE_URL=http://host:11434/v1 COPILOT_MODEL=$M copilot -p ...`

Zed agent (headless): `eval-cli --workdir . --model anthropic/$M --instruction "$PROMPT" --output-dir $LOG`

Copilot coding agent (async, on GitHub): assign the GitHub issue to Copilot; the delivery gate tracks
the PR.

## After the run

Log framework, provider, model, tokens, cost and outcome to `~/.hermes/autonomy/code_runs.jsonl`, run the
repo's tests yourself, and hand over through the kanban delivery gate as usual.

## Benchmarking

`cd ~/hermes-enhancements/bench && python -m hbench matrix matrix.toml` runs the grid;
`python -m hbench report results/*.jsonl` prints the leaderboard. Run it only when the Claude quota mode
is `idle`, and send Filip the leaderboard with any proposed change to `coding_routing.yaml`.
