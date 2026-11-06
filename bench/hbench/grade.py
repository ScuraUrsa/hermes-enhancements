"""Grading: restore hidden tests, run the verify (and regression) command."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from . import workspace
from .tasks import Task

_COUNTS = re.compile(r"(\d+) (passed|failed|errors?|skipped)")


def run_shell(cmd: str, cwd: Path, timeout: int, log: Path) -> tuple[int | None, str]:
    try:
        p = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            executable="/bin/bash",
        )
        out, code = p.stdout + p.stderr, p.returncode
    except subprocess.TimeoutExpired as e:
        out, code = f"{e.stdout or ''}{e.stderr or ''}\n[hbench] timed out after {timeout}s", None
    log.write_text(out if isinstance(out, str) else out.decode(errors="replace"))
    return code, out if isinstance(out, str) else out.decode(errors="replace")


def pytest_counts(output: str) -> dict:
    counts = {"tests_passed": 0, "tests_failed": 0}
    for n, kind in _COUNTS.findall(output.splitlines()[-1] if output.strip() else ""):
        if kind == "passed":
            counts["tests_passed"] = int(n)
        elif kind in ("failed", "error", "errors"):
            counts["tests_failed"] += int(n)
    return counts


def grade(task: Task, src: Path, ws: Path, outdir: Path) -> dict:
    workspace.restore_from_fix(task, src, ws, task.hidden_tests)
    code, out = run_shell(task.verify, ws, task.verify_timeout, outdir / "verify.log")
    result = {"verify_exit": code, "solved": code == 0, **pytest_counts(out)}
    if task.regression:
        rcode, _ = run_shell(task.regression, ws, task.verify_timeout, outdir / "regression.log")
        result["regression_exit"] = rcode
        result["solved"] = result["solved"] and rcode == 0
    return result
