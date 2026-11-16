"""Agent adapters: one per coding framework.

An adapter builds the headless command line and environment for its framework
from (provider, model), runs it in the workspace with a timeout, and parses the
framework's own output into the common metrics below. Any metric a framework
does not report stays ``None``.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from ..providers import Provider
from ..tasks import Task

METRIC_KEYS = (
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
    "cost_usd",  # as reported by the framework (None for local models)
    "turns",
    "tool_calls",
    "agent_status",
)


class UnsupportedProvider(Exception):
    pass


@dataclass
class RunContext:
    task: Task
    src: Path  # local clone of the task's source repo
    workspace: Path
    outdir: Path
    provider: Provider
    model: str
    timeout: int
    options: dict = field(default_factory=dict)


@dataclass
class AgentResult:
    exit_code: int | None
    timed_out: bool
    duration_sec: float
    metrics: dict


class Agent:
    name = "base"
    binary: str | None = None
    provider_kinds: tuple[str, ...] = ()

    def bin(self, ctx: RunContext) -> str:
        return ctx.options.get("binary") or self.binary or self.name

    def available(self) -> bool:
        return self.binary is None or shutil.which(self.binary) is not None

    def command(self, ctx: RunContext) -> tuple[list[str], dict[str, str]]:
        raise NotImplementedError

    def parse(self, ctx: RunContext, stdout_path: Path) -> dict:
        return {}

    def run(self, ctx: RunContext) -> AgentResult:
        if ctx.provider.kind not in self.provider_kinds:
            raise UnsupportedProvider(f"{self.name} cannot use provider kind {ctx.provider.kind!r}")
        argv, env_updates = self.command(ctx)
        argv += list(ctx.options.get("extra_args", []))
        env = {**os.environ, **env_updates}
        for k, v in env_updates.items():
            if v is None:
                env.pop(k, None)
        (ctx.outdir / "command.txt").write_text(" ".join(a if len(a) < 200 else a[:200] + "..." for a in argv) + "\n")
        stdout_path = ctx.outdir / "agent.stdout"
        stderr_path = ctx.outdir / "agent.stderr"
        start = time.monotonic()
        timed_out = False
        with stdout_path.open("wb") as out, stderr_path.open("wb") as err:
            proc = subprocess.Popen(
                argv,
                cwd=ctx.workspace,
                env=env,
                stdout=out,
                stderr=err,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
            try:
                proc.wait(timeout=ctx.timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
        duration = time.monotonic() - start
        try:
            metrics = self.parse(ctx, stdout_path)
        except Exception as e:  # a parser bug must not lose the run
            metrics = {"parse_error": repr(e)}
        if ctx.provider.local:
            metrics["cost_usd"] = None
        return AgentResult(proc.returncode, timed_out, duration, metrics)
