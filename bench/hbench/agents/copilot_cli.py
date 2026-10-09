"""GitHub Copilot CLI (``copilot -p``, npm ``@github/copilot``).

Providers:

* ``github``    - GitHub-hosted models under the Copilot subscription
                  (auth: ``COPILOT_GITHUB_TOKEN`` > ``GH_TOKEN`` > ``GITHUB_TOKEN``).
* ``ollama`` / ``openai`` / ``anthropic`` - BYOK, supported since April 2026
  (https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/use-byok-models):
  ``COPILOT_PROVIDER_BASE_URL`` + ``COPILOT_MODEL``. Ollama needs ``/v1``
  appended and a model that handles Copilot's ~38 tools; reports say mid-size
  local models struggle, which is exactly what this benchmark should show.

``--output-format json`` is what Harbor's Copilot adapter uses; the event
schema is not documented, so parsing below is best-effort and the raw stream is
always kept in ``agent.stdout``.
"""

from __future__ import annotations

import json
from pathlib import Path

from .base import Agent, RunContext


class CopilotCli(Agent):
    name = "copilot-cli"
    binary = "copilot"
    provider_kinds = ("github", "ollama", "openai", "anthropic")

    def command(self, ctx: RunContext):
        p = ctx.provider
        argv = [self.bin(ctx), "-p", ctx.task.prompt(), "--allow-all-tools", "--no-color"]
        if ctx.options.get("json_output", True):
            argv += ["--output-format", "json"]
        env: dict[str, str | None] = {}
        if p.kind == "github":
            argv += ["--model", ctx.model]
        else:
            default = "https://api.anthropic.com" if p.kind == "anthropic" else "http://localhost:11434"
            base = p.base_url or default
            if p.kind == "ollama" and not base.rstrip("/").endswith("/v1"):
                base = base.rstrip("/") + "/v1"
            env.update(
                {
                    "COPILOT_PROVIDER_BASE_URL": base,
                    "COPILOT_PROVIDER_TYPE": "anthropic" if p.kind == "anthropic" else "openai",
                    "COPILOT_MODEL": ctx.model,
                }
            )
            if p.api_key:
                env["COPILOT_PROVIDER_API_KEY"] = p.api_key
            if p.local:
                env["COPILOT_OFFLINE"] = "true"
            if p.context_tokens:
                env["COPILOT_PROVIDER_MAX_PROMPT_TOKENS"] = str(p.context_tokens)
        return argv, env

    def parse(self, ctx: RunContext, stdout_path: Path) -> dict:
        tool_calls = 0
        usage: dict = {}
        events = 0
        for line in stdout_path.read_text(errors="replace").splitlines():
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            events += 1
            text = json.dumps(ev)
            if '"tool' in text and ('"call' in text or '"start' in text):
                tool_calls += 1
            for key in ("usage", "tokenUsage", "token_usage"):
                if isinstance(ev.get(key), dict):
                    usage = ev[key]
        return {
            "tool_calls": tool_calls or None,
            "input_tokens": usage.get("input_tokens") or usage.get("inputTokens"),
            "output_tokens": usage.get("output_tokens") or usage.get("outputTokens"),
            "agent_status": f"{events} json events",
        }
