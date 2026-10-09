# hbench: coding frameworks × model providers, on Hermes' own work

Status: design + runnable skeleton (2026-10-09). Nothing has been run against a real model yet.

## 1. What we want to know

Filip wants Hermes to code through whole coding *frameworks* (Claude Code, GitHub Copilot, Zed), not
only through a bare model, and to run those frameworks on more than one provider (Anthropic and Ollama
first, more later). The benchmark has to answer three questions:

1. **Which model?** Same framework, different providers/models (Claude Code on Anthropic vs Claude Code
   on Ollama).
2. **Which framework?** Same model, different frameworks (qwen3-coder in Claude Code vs Copilot CLI vs
   Zed).
3. **Which combination for which job?** Pass rate, time and cost per *task category* (small bug fix,
   multi-file fix, tests, infra, greenfield), which becomes Hermes' routing table.

## 2. Starting point: 10x-bench and related work

**[przeprogramowani/10x-bench](https://github.com/przeprogramowani/10x-bench)** (MIT) is a single-task
leaderboard: one 50-word Polish prompt asks the model to build the Przeprogramowani.pl website (Astro +
React + Tailwind, Cloudflare-ready, real podcast/YouTube content looked up on the web). It is scored on a
10-point rubric ([10x-bench-eval](https://github.com/przeprogramowani/10x-bench-eval)/`criteria.md`):
deterministic checks (build, `wrangler deploy --dry-run`, YouTube oEmbed), an Opus judge for content, and a
human for UI/responsiveness. A failed build scores 0.

What we take from it:

* **The greenfield track idea and its rubric**: one realistic "build the whole thing" task, a build-gate
  that zeroes the score, deterministic checks first, an LLM judge only for what can't be checked.
* **Its harness lesson**: 10x-bench says outright that "model" and "harness" are one combination. Its
  Docker runner (`images/harness/run-attempt`) runs `claude -p`, `codex exec` and `opencode run` per
  attempt in a throwaway container.

What it lacks for our questions: no Ollama or base-URL plumbing, no token/cost capture for Claude Code,
no Zed or Copilot, only one task, and model and harness are never varied independently.

Related work that is more useful for the harness side:

* **[Harbor](https://github.com/laude-institute/harbor)** (Apache-2.0, Terminal-Bench authors):
  containerised agent eval with adapters for Claude Code (already handles `ANTHROPIC_BASE_URL` and pins
  every model alias), Copilot CLI (`copilot --prompt … --yolo --output-format=json`), Codex, OpenCode,
  Aider, OpenHands and any ACP agent; has an `ollama` provider; tasks are a Dockerfile + instruction +
  test script. hbench copies its key adapter decisions; our tasks could be exported to Harbor's format
  later if we want its cloud runners.
* **[Zed `crates/eval_cli`](https://github.com/zed-industries/zed/tree/main/crates/eval_cli)** (GPL-3.0):
  the only headless way to run Zed's agent. Same `NativeAgent` loop as the editor, writes `result.json`
  with tokens, steps and tool calls; takes OpenAI-compatible endpoints through
  `ZED_OPENAI_COMPATIBLE_PROVIDERS`. Zed uses it for its own Terminal-Bench runs.
* SWE-bench / Terminal-Bench / Aider polyglot: the "hidden tests decide" model we use for track A.

## 3. Benchmark design

### 3.1 Tracks

| Track | What | Graded by | Status |
|---|---|---|---|
| **A. Hermes fixes** | Real bug-fix commits from Filip's repos, reverted. The agent gets an issue-style report; the fix commit's tests are hidden and restored only for grading. | Hidden pytest (+ optional regression suite) | **7 tasks, validated** |
| B. Hermes features & tests | Spec tasks from code with no tests (cc_run.py, quota_governor, contact-crm parsers), Terraform/Ansible/Packer fixes | Hidden reference suites, mutation score (mutmut), `terraform validate`/`tflint`, `ansible-lint`, `packer validate` | backlog (§3.4) |
| C. Greenfield (10x-bench style) | One "build the app" prompt per stack (10x-bench's own website task, plus e.g. a Home Assistant add-on) | Build gate + scripted checks + LLM judge from 10x-bench-eval's rubric | later |
| D. Hermes kanban end-to-end | A real kanban card → branch → PR, through the delivery gate | Delivery gate + CI green + reviewer | later, once Hermes routes through hbench adapters (§6) |

Track A comes first because it is objective, cheap to grade and private: the crewai-orchestrator and
WOBI commits never left Filip's repos, so they can't be in any model's training data. hermes-agent tasks
are upstream NousResearch commits and are flagged `visibility = "public"` (contamination risk; report
them separately).

### 3.2 How one attempt runs

```
task.toml + instruction.md
   │
   ▼  workspace.prepare: git archive <fix>^ → fresh repo with ONE commit (no history, no fix, no hidden tests)
   ▼  setup: e.g. uv venv + pytest (before the agent, so it can run tests)
   ▼  agent adapter: headless framework with a timeout, isolated config dir, env for the chosen provider
   ▼  diff_stats: patch, files/lines changed
   ▼  grade: restore hidden tests from the fix commit, run verify (+ regression) → solved true/false
   ▼  result.json + one line in results/*.jsonl
```

`hbench validate` keeps tasks honest: the **oracle** (applies the real fix) must pass and the **no-op**
must fail. All 7 tasks pass this today.

### 3.3 Metrics (per attempt)

* `solved` (the headline), `tests_passed/failed`, `timed_out`, `harness error` (not counted against the agent)
* `duration_sec`, `turns`, `tool_calls`, `input/output/cache tokens` (whatever the framework reports)
* `cost_usd` as the framework reports it; forced to `None` for local providers (Claude Code would price
  local tokens at Anthropic list price). Local runs record `hardware` instead.
* `files_changed`, `lines_added/removed`, and the full `agent.patch` for review

Leaderboard (`hbench report`): pass rate, median time, median output tokens, total cost and **$ per
solved task**, pass rate per category, and a task × combination grid. With `repeats ≥ 3`, compare pass
rates rather than single runs; agents are not deterministic.

### 3.4 Task inventory

Validated (oracle passes, no-op fails):

| Task | Repo / fix | Category | Difficulty |
|---|---|---|---|
| crewai-delivery-red-ci | crewai-orchestrator `97f1ec5` | bugfix (behaviour) | medium |
| crewai-kanban-schema-drift | crewai-orchestrator `6e373a0` | bugfix (sqlite schema + idempotency) | medium |
| crewai-merge-safety-merge-base | crewai-orchestrator `aafae79` | bugfix (git) | easy |
| crewai-status-none-safe | crewai-orchestrator `7996bb3` | bugfix (crash) | easy |
| wobi-triage-policy-shape | WOBI `3d9e582` | bugfix (config) | easy |
| hermes-tool-name-xml-leak | hermes-agent `132d6fe` (public) | bugfix (parsing) | easy |
| hermes-file-tools-worktree-cwd | hermes-agent `e45b745` (public) | bugfix (path resolution) | hard |

Verified candidates still to package (tests fail before the fix and pass after):

* hermes-agent `aa6f277` (memory sync off the turn thread, 13 tests), `02a4d66` (retry transient
  transport error), `8e223b3` (protect built-in skills from archival), `e02f4c0` (`--replace` aborts when
  the old PID survives), `3714caa` (compression continuations in transcripts), `cb5c24e`
* crewai-orchestrator `e6dd0ea`, `d3cef78` (delivery gate notifications), `b536d6a` (yt-dlp as a
  module; a feature specified by tests), `4e163d2` (new `check_profile_budgets.py`, feature), `06715e4`

Track B ideas, need a written reference solution or mutation grading:

* hermes-infra: make the VBoxManage path configurable (2 tests fail on Linux today: a real, open bug)
* WOBI: tests for `cc_run.py` (stream-json parsing, rate-limit state, exit codes 75/77) and
  `quota_governor.hold_reason()`, graded by mutation score
* hermes-contact-crm: tests for `whatsapp_parser.py` and `alias_resolver.py`
* hermes-agent: tests for the fork's `agent/provider_semaphore.py`; add a tool via `registry.register` +
  `toolsets.py`
* terraforge-modules: add `versions.tf` with an azurerm pin, graded by `terraform validate` + `tflint`
* crewai-orchestrator: replace `datetime.utcnow()`, graded with `-W error::DeprecationWarning`
* hermes-trade: implement a backtest strategy, graded by hidden tests + ruff + mypy

**Not usable for cloud providers until cleaned:** `hermes-config-backup` has `.env` and `auth.json`
committed, and `terraforge-modules` has `ssh/id_rsa` committed. No task uses them; those secrets should
be rotated regardless.

## 4. Frameworks and providers

| Framework | Headless entry point | Anthropic | Ollama (local / cloud) | Other |
|---|---|---|---|---|
| **Claude Code** | `claude -p … --output-format stream-json --permission-mode …` | native | `ANTHROPIC_BASE_URL=http://host:11434`: Ollama speaks the Anthropic Messages API since v0.14 ([docs](https://docs.ollama.com/integrations/claude-code)); no prompt caching, `tool_choice` unsupported, ≥64k context recommended | any Anthropic-compatible proxy (LiteLLM) |
| **GitHub Copilot CLI** | `copilot -p … --allow-all-tools [--output-format json]` | BYOK (`COPILOT_PROVIDER_TYPE=anthropic`) | BYOK since April 2026: `COPILOT_PROVIDER_BASE_URL=http://host:11434/v1`, `COPILOT_MODEL` ([docs](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/use-byok-models)); needs strong tool calling (~38 tools; [field report](https://dev.classmethod.jp/articles/copilot-cli-byok-ollama-local-model/) saw mid-size local models fail) | GitHub-hosted models on the Copilot subscription (separate quota pool) |
| **Zed agent** | `eval-cli --workdir … --model provider/model --instruction …` (built from the Zed repo) | native | through `ZED_OPENAI_COMPATIBLE_PROVIDERS` → Ollama `/v1` | any OpenAI-compatible endpoint |
| Copilot coding agent (cloud) | assign a GitHub issue to Copilot | GitHub's model picker | no | runs on GitHub, 59-min sessions; compared separately, not in the local harness |

Notes:

* **Zed has no headless mode in the editor.** `eval-cli` runs the same agent loop and is what Zed itself
  benchmarks with, so it is the fair way to put "Zed" in the matrix. Zed the *editor* stays Filip's
  interactive tool; it already talks to Hermes the other way round (Hermes is an ACP server in
  `acp_adapter/`).
* Running Claude Code *inside* Zed (Zed as an ACP client) benchmarks Claude Code, not Zed.
* Each Claude Code run gets its own `CLAUDE_CONFIG_DIR`, so Filip's CLAUDE.md, memory, plugins and MCP
  servers don't skew results. When routing to Ollama, every model alias (sonnet/opus/haiku/subagents) is
  pinned to the benchmarked model and the subscription token is removed from the environment.
* Ollama's default context window is tiny for agents; set `OLLAMA_CONTEXT_LENGTH=65536` (or more) on the
  server, or results measure truncation, not the model.
* Copilot CLI's JSON output schema isn't documented; hbench keeps the raw stream and parses it
  best-effort. First real run should confirm the token fields.

## 5. Where it lives and where it runs

**Recommendation: keep it in `hermes-enhancements/bench/` for now, move it to its own private repo
(`hermes-bench`) once the first real matrix has run and Hermes starts importing its adapters.** It is a
self-contained folder with no dependencies outside the standard library, so moving it is a `git
filter-repo` away. Tasks reference other repos by commit; they don't copy code.

Where it runs:

* **Dev VM** (where Hermes' coding work moved tonight): runs the harness, all repos are already checked
  out there (`HBENCH_REPOS=/home/ubuntu`), and it has the Claude and GitHub credentials. 6 GB of RAM is
  enough for the harness and cloud providers; run attempts one at a time.
* **Local Ollama models need a GPU**, which the VMs don't have. Serve Ollama from Filip's PC (`D:\hermes`)
  on the host-only network (`OLLAMA_HOST=0.0.0.0`, reachable as `192.168.56.1:11434` from the VMs; see
  `providers.toml` → `ollama-pc`) and point the dev VM's harness at it. Ollama Cloud
  (`deepseek-v4-pro`, already Hermes' default model) works from the VM directly.
* **Isolation**: agents run with permissions bypassed. Run inside the `docker/Dockerfile` image (non-root,
  only the repos mounted read-only, only one provider's keys), not on a VM that holds Filip's other
  secrets.
* **Budget**: Filip chose to run Anthropic cells on the Claude Code subscription, alongside Hermes' other
  work. Every result line records the cost Claude Code reports (an API-price equivalent on a
  subscription), so the first run shows what each cell would cost on an API key.

## 6. Hermes using these frameworks

What exists today:

* `WOBI/…/hermes_backup/files/scripts/cc_run.py` is "the ONE way Hermes runs Claude Code": `claude -p
  --output-format stream-json`, rate-limit tracking in `~/.hermes/autonomy/quota/claude.json`, one line
  per run in `claude_runs.jsonl`. The `coder` profile shells out to it.
* `quota_governor.py` *holds* coder tasks when Claude's quota is exhausted.
* Copilot is wired only as a **model provider** for Hermes itself (`copilot-acp`: `copilot --acp
  --stdio`), not as a coding framework. Zed is a client of Hermes (ACP), not a tool Hermes drives.

Plan:

1. **One runner, many frameworks.** Generalise `cc_run.py` into `code_run.py --framework
   claude-code|copilot-cli|zed --provider … --model …`, building commands with hbench's adapters
   (`hbench.agents`), so the benchmark and production run frameworks exactly the same way. Keep
   `cc_run.py`'s rate-limit handling; log to `code_runs.jsonl` with framework/provider/model added.
2. **Routing from evidence.** `hbench report --json` → a routing table `~/.hermes/coding_routing.yaml`:
   per task category and difficulty, an ordered list of (framework, provider, model). Filip approves
   changes to it.
3. **Fallback instead of holding.** When Claude's quota is exhausted, `quota_governor` moves to the next
   entry (e.g. Copilot CLI on the GitHub quota, then Claude Code on Ollama Cloud or the PC) instead of
   parking the card. That is the practical payoff of supporting several providers.
4. **Kanban lanes.** `coder` resolves through the routing table; explicit lanes `coder-cc`,
   `coder-copilot`, `coder-zed` force one framework (useful for A/B on real cards, i.e. track D).
5. **Copilot coding agent** for well-specified GitHub issues: Hermes assigns the issue to Copilot, and
   the existing delivery gate tracks the PR like any other. It costs no VM resources.
6. **Benchmark as routine.** A Hermes skill (`hermes-skill/coding-frameworks/SKILL.md`, draft in this
   folder) teaches Hermes the commands; a weekly cron on the dev VM runs a small matrix, and a new model
   in Ollama's library or a new Claude/Copilot release triggers a run, with the leaderboard sent to
   Filip and a proposed routing-table change.

## 7. Which to use for what (priors, until the data says otherwise)

These are starting hypotheses, written down so the first matrix can confirm or overturn them:

| Job | First choice | Why | Fallback |
|---|---|---|---|
| Multi-file bug fixes, hermes-agent core, anything risky | Claude Code + Anthropic (Sonnet/Opus) | strongest agent loop and models; Hermes' existing path | Copilot CLI on a Claude model (GitHub quota) |
| Small, well-specified fixes and test writing | Claude Code + Ollama Cloud (deepseek-v4-pro) or Copilot CLI | cheap, separate quota | Claude Code + local Ollama |
| Offline / private / free | Claude Code + local Ollama on the PC | Claude Code's tool set is small enough for local models | Zed eval-cli + local Ollama |
| Async issue → PR | Copilot coding agent | runs on GitHub, no local resources | Hermes kanban `coder` |
| Interactive editing by Filip | Zed editor (with Hermes over ACP) | it's an editor, not a background worker | – |

Things the benchmark should specifically settle: whether local models in the 20–35B range can solve
even the easy track-A tasks inside Claude Code; whether Copilot CLI's larger tool surface hurts local
models as the field report suggests; and whether Zed's agent loop is competitive with the same model.

## 8. Decisions and next steps

Decided by Filip (2026-10-09): Claude runs use the Claude Code subscription, alongside Hermes' other
work; "Ollama" means **Ollama Cloud**. First-run models are in `matrix.example.toml` (glm-5.3,
kimi-k2.7-code, minimax-m3, deepseek-v4-pro, glm-5.3-flash, plus Claude opus and sonnet).

1. Run `hbench validate` and the first 1-repeat matrix on the dev VM, inside the Docker image.
2. Build Zed's `eval-cli` (heavy Rust build: do it on the PC or in CI, not on the 6 GB VM) and add the
   Zed cell; add the Copilot-hosted cell if a Copilot subscription is available.
3. Package the remaining verified track-A candidates (§3.4) to reach ~20 tasks; add track B graders;
   raise `repeats` to 3 for decisions.
4. Build `code_run.py` on top of `hbench.agents` and the routing table (§6).
