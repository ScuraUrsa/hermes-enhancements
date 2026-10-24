"""Zed's agent, headless, through Zed's own ``eval-cli``.

The Zed editor has no headless agent mode; ``crates/eval_cli`` in the Zed repo
runs the same NativeAgent + AcpThread loop without a GUI and is what Zed uses
for its own Terminal-Bench / SWE runs. Build it once (about 27 min on 4 cores, 15 GB RAM;
not on the 6 GB dev VM), or use the prebuilt binary below:

    git clone https://github.com/zed-industries/zed && cd zed
    cargo build --release -p eval_cli   # -> target/release/eval-cli

It writes ``result.json`` (status, duration, tokens, step and tool-call counts)
to ``--output-dir``. Non-Anthropic endpoints are registered through the
``ZED_OPENAI_COMPATIBLE_PROVIDERS`` env var (same JSON shape as Zed's
``language_models.openai_compatible`` setting), which is how Ollama's ``/v1`` is
plugged in here; Zed reads that provider's key from ``<ID>_API_KEY`` (``HBENCH_API_KEY``,
see ``crates/language_models/src/provider/api_compatible.rs``).

A prebuilt static binary (Zed f16f965) is on this repo's ``tools/zed-eval-cli`` branch.
"""

from __future__ import annotations

import json
from pathlib import Path

from .base import Agent, RunContext

PROVIDER_ID = "hbench"


class Zed(Agent):
    name = "zed"
    binary = "eval-cli"
    provider_kinds = ("anthropic", "ollama", "openai")

    def command(self, ctx: RunContext):
        p = ctx.provider
        out = ctx.outdir / "zed"
        out.mkdir(exist_ok=True)
        env: dict[str, str | None] = {}
        if p.kind == "anthropic":
            model = f"anthropic/{ctx.model}"
            if p.api_key:
                env["ANTHROPIC_API_KEY"] = p.api_key
        else:
            base = p.base_url or "http://localhost:11434"
            if p.kind == "ollama" and not base.rstrip("/").endswith("/v1"):
                base = base.rstrip("/") + "/v1"
            env["ZED_OPENAI_COMPATIBLE_PROVIDERS"] = json.dumps(
                {
                    PROVIDER_ID: {
                        "api_url": base,
                        "available_models": [
                            {
                                "name": ctx.model,
                                "max_tokens": p.context_tokens or 65536,
                                "capabilities": {
                                    "tools": True,
                                    "images": False,
                                    "parallel_tool_calls": False,
                                    "prompt_cache_key": False,
                                },
                            }
                        ],
                    }
                }
            )
            env[f"{PROVIDER_ID.upper()}_API_KEY"] = p.api_key or "ollama"
            model = f"{PROVIDER_ID}/{ctx.model}"
        argv = [
            self.bin(ctx),
            "--workdir",
            str(ctx.workspace),
            "--model",
            model,
            "--instruction",
            ctx.task.prompt(),
            "--timeout",
            str(ctx.timeout),
            "--output-dir",
            str(out),
        ]
        return argv, env

    def parse(self, ctx: RunContext, stdout_path: Path) -> dict:
        f = ctx.outdir / "zed" / "result.json"
        if not f.exists():
            return {"agent_status": "no_result_json"}
        r = json.loads(f.read_text())
        return {
            "input_tokens": r.get("input_tokens"),
            "output_tokens": r.get("output_tokens"),
            "cache_read_tokens": r.get("cache_read_input_tokens"),
            "cache_write_tokens": r.get("cache_creation_input_tokens"),
            "turns": r.get("step_count"),
            "tool_calls": r.get("tool_call_count"),
            "agent_status": r.get("status"),
        }
