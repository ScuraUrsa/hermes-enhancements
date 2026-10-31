# hbench

Benchmark **coding frameworks** (Claude Code, GitHub Copilot CLI, Zed's agent) × **model providers**
(Anthropic, Ollama local/cloud, GitHub-hosted, any OpenAI-compatible endpoint) on tasks taken from the
Hermes repositories. Design, research and recommendations: [DESIGN.md](DESIGN.md).

Standard library only (Python ≥ 3.11). Tasks reference real commits in Filip's repos; the agent works
in a fresh, history-free copy of the code before the fix, and the fix's own tests are hidden until
grading.

## Quick start (dev VM)

```bash
cd hermes-enhancements/bench
export HBENCH_REPOS=/home/ubuntu          # where the Hermes repos are checked out (else cloned from GitHub)
python -m hbench doctor                   # which frameworks are installed, which providers are reachable
python -m hbench list
python -m hbench validate                 # oracle must pass, no-op must fail, for every task

# one combination on the easy tasks
export CLAUDE_CODE_OAUTH_TOKEN=...        # or ANTHROPIC_API_KEY
python -m hbench run -a claude-code -p anthropic -m sonnet -t 'tag:private' -n 3
python -m hbench run -a claude-code -p ollama-pc -m qwen3-coder:30b -t crewai-status-none-safe

# the full grid, then the leaderboard
cp matrix.example.toml matrix.toml && $EDITOR matrix.toml
python -m hbench matrix matrix.toml
python -m hbench report results/*.jsonl
```

Agents run with permissions bypassed: use the container in `docker/Dockerfile` (non-root, repos
mounted read-only, one provider's keys) rather than a machine that holds other secrets.

Every attempt leaves `results/attempts/<task>/<agent>__<provider>__<model>__<id>/` with `prompt.md`,
`command.txt`, `agent.stdout` (the raw trajectory), `agent.patch`, `verify.log` and `result.json`.

## Layout

```
hbench/            runner, grading, report, CLI
hbench/agents/     claude_code.py, copilot_cli.py, zed.py, reference.py (oracle / noop)
tasks/<id>/        task.toml (repo, fix commit, hidden tests, setup, verify) + instruction.md
providers.toml     where models run (no secrets: names of env vars only)
matrix.example.toml framework × provider × model grid
hermes-skill/      draft Hermes skill for driving the frameworks
docker/Dockerfile  sandbox image
tests/             harness tests (fake agents, no network): python -m pytest tests
```

## Adding a task

1. Find a fix commit whose tests fail on its parent and pass on it.
2. `tasks/<id>/task.toml`: `repo`, `fix_commit`, `hidden_tests` (test files to restore from the fix),
   `[setup] command`, `[verify] command`; `visibility = "public"` for upstream commits.
3. `tasks/<id>/instruction.md`: the symptom, like an issue report, plus any names the hidden tests
   import. Don't describe the fix.
4. `python -m hbench validate -t <id>` must print `OK`.

## Adding a framework

Subclass `hbench.agents.base.Agent`: `command()` returns argv + env for a (provider, model), `parse()`
turns the framework's output into the common metrics. Register it in `hbench/agents/__init__.py`.
Candidates: Codex CLI, OpenCode, Aider, Gemini CLI (Harbor has adapters for all of them to copy from).
