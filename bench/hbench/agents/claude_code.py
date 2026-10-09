"""Claude Code (``claude -p``), against Anthropic or any Anthropic-compatible API.

Ollama serves the Anthropic Messages API natively since v0.14
(https://docs.ollama.com/integrations/claude-code), so the Ollama route is just
``ANTHROPIC_BASE_URL``. Every model alias Claude Code might pick on its own
(sonnet/opus/haiku, subagents) is pinned to the benchmarked model so a run
never silently mixes models.

Each run gets its own ``CLAUDE_CONFIG_DIR`` so the user's CLAUDE.md, memory,
plugins and MCP servers don't leak into the benchmark. Authenticate with
``ANTHROPIC_API_KEY`` or ``CLAUDE_CODE_OAUTH_TOKEN`` (from ``claude setup-token``;
on Hermes this is Bitwarden's ``CLAUDE_SETUP_TOKEN``).
"""

from __future__ import annotations

import json
from pathlib import Path

from .base import Agent, RunContext


class ClaudeCode(Agent):
    name = "claude-code"
    binary = "claude"
    provider_kinds = ("anthropic", "ollama", "openai")

    def command(self, ctx: RunContext):
        p = ctx.provider
        argv = [
            self.bin(ctx),
            "-p",
            ctx.task.prompt(),
            "--output-format",
            "stream-json",
            "--verbose",
            "--permission-mode",
            ctx.options.get("permission_mode", "bypassPermissions"),
            "--model",
            ctx.model,
        ]
        if "max_turns" in ctx.options:
            argv += ["--max-turns", str(ctx.options["max_turns"])]
        if "effort" in ctx.options:
            argv += ["--effort", str(ctx.options["effort"])]
        cfg_dir = ctx.outdir / "claude-config"
        cfg_dir.mkdir(exist_ok=True)
        env = {
            "CLAUDE_CONFIG_DIR": str(cfg_dir),
            "DISABLE_AUTOUPDATER": "1",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        }
        if p.kind == "anthropic":
            if p.base_url:
                env["ANTHROPIC_BASE_URL"] = p.base_url
            if p.api_key:
                env["ANTHROPIC_API_KEY"] = p.api_key
        else:  # ollama / openai-compatible proxy speaking the Anthropic API
            env.update(
                {
                    "ANTHROPIC_BASE_URL": p.base_url or "http://localhost:11434",
                    "ANTHROPIC_AUTH_TOKEN": p.api_key or "ollama",
                    "ANTHROPIC_API_KEY": "",
                    "CLAUDE_CODE_OAUTH_TOKEN": None,  # never send the subscription token elsewhere
                    "ANTHROPIC_DEFAULT_SONNET_MODEL": ctx.model,
                    "ANTHROPIC_DEFAULT_OPUS_MODEL": ctx.model,
                    "ANTHROPIC_DEFAULT_HAIKU_MODEL": ctx.model,
                    "CLAUDE_CODE_SUBAGENT_MODEL": ctx.model,
                }
            )
        return argv, env

    def parse(self, ctx: RunContext, stdout_path: Path) -> dict:
        tool_calls = 0
        result = None
        for line in stdout_path.read_text(errors="replace").splitlines():
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("type") == "assistant":
                for block in (ev.get("message") or {}).get("content") or []:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tool_calls += 1
            elif ev.get("type") == "result":
                result = ev
        m = {"tool_calls": tool_calls}
        if result:
            usage = result.get("usage") or {}
            m.update(
                {
                    "input_tokens": usage.get("input_tokens"),
                    "output_tokens": usage.get("output_tokens"),
                    "cache_read_tokens": usage.get("cache_read_input_tokens"),
                    "cache_write_tokens": usage.get("cache_creation_input_tokens"),
                    "cost_usd": result.get("total_cost_usd"),
                    "turns": result.get("num_turns"),
                    "agent_status": (result.get("subtype") or "?") + (" (error)" if result.get("is_error") else ""),
                }
            )
        else:
            m["agent_status"] = "no_result_event"
        return m
