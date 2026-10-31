"""Run one (task, agent, provider, model) attempt end to end, and run matrices."""

from __future__ import annotations

import json
import platform
import shutil
import time
import tomllib
import uuid
from datetime import UTC, datetime
from pathlib import Path

from . import grade, workspace
from .agents import AGENTS, RunContext, UnsupportedProvider
from .providers import Provider
from .tasks import Task, select

NO_PROVIDER = Provider(name="none", kind="none")


def run_attempt(
    task: Task,
    agent_name: str,
    provider: Provider,
    model: str,
    out_root: Path,
    options: dict | None = None,
    keep_workspace: bool = False,
) -> dict:
    agent = AGENTS[agent_name]()
    attempt_id = f"{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:6]}"
    outdir = out_root / "attempts" / task.id / f"{agent_name}__{provider.name}__{model.replace('/', '_')}__{attempt_id}"
    outdir.mkdir(parents=True)
    ws = outdir / "ws"
    record = {
        "attempt_id": attempt_id,
        "started_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "task": task.id,
        "category": task.category,
        "difficulty": task.difficulty,
        "visibility": task.visibility,
        "agent": agent_name,
        "provider": provider.name,
        "provider_kind": provider.kind,
        "model": model,
        "hardware": provider.hardware,
        "host": platform.node(),
        "options": options or {},
        "outdir": str(outdir),
    }
    try:
        src = workspace.resolve_repo(task)
        base = workspace.prepare(task, src, ws)
        if task.setup:
            code, _ = grade.run_shell(task.setup, ws, task.setup_timeout, outdir / "setup.log")
            if code != 0:
                raise RuntimeError(f"setup failed (exit {code}), see setup.log")
        (outdir / "prompt.md").write_text(task.prompt())
        ctx = RunContext(
            task,
            src,
            ws,
            outdir,
            provider,
            model,
            timeout=int((options or {}).get("timeout", task.agent_timeout)),
            options=options or {},
        )
        res = agent.run(ctx)
        record.update(
            {
                "agent_exit": res.exit_code,
                "timed_out": res.timed_out,
                "duration_sec": round(res.duration_sec, 1),
                **res.metrics,
            }
        )
        record.update(workspace.diff_stats(ws, base, outdir / "agent.patch"))
        t0 = time.monotonic()
        record.update(grade.grade(task, src, ws, outdir))
        record["verify_sec"] = round(time.monotonic() - t0, 1)
    except UnsupportedProvider as e:
        record.update({"solved": None, "error": str(e)})
    except Exception as e:  # harness error, not an agent failure
        record.update({"solved": None, "error": f"{type(e).__name__}: {e}"})
    finally:
        if not keep_workspace and ws.exists():
            shutil.rmtree(ws, ignore_errors=True)
    (outdir / "result.json").write_text(json.dumps(record, indent=2))
    return record


def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(record) + "\n")


def expand_matrix(matrix_path: Path) -> tuple[list[dict], list[str] | None, int]:
    """``matrix.toml`` -> list of cells {agent, provider, model, options}."""
    m = tomllib.loads(matrix_path.read_text())
    cells = []
    for c in m.get("cell", []):
        models = c.get("models") or [c["model"]]
        for model in models:
            cells.append(
                {
                    "agent": c["agent"],
                    "provider": c["provider"],
                    "model": model,
                    "options": c.get("options", {}),
                    "tasks": c.get("tasks"),
                }
            )
    return cells, m.get("tasks"), int(m.get("repeats", 1))


def run_matrix(matrix_path: Path, tasks: list[Task], providers: dict[str, Provider], out_root: Path, log=print) -> Path:
    cells, task_patterns, repeats = expand_matrix(matrix_path)
    results = out_root / f"run-{datetime.now(UTC):%Y%m%dT%H%M%S}.jsonl"
    for cell in cells:
        provider = providers[cell["provider"]]
        for task in select(select(tasks, task_patterns), cell["tasks"]):
            for i in range(repeats):
                log(f"[hbench] {task.id} :: {cell['agent']} / {provider.name} / {cell['model']} (#{i + 1})")
                rec = run_attempt(task, cell["agent"], provider, cell["model"], out_root, cell["options"])
                rec["repeat"] = i
                append_jsonl(results, rec)
                log(f"[hbench]   solved={rec.get('solved')} {rec.get('duration_sec', '-')}s {rec.get('error', '')}")
    return results


__all__ = ["NO_PROVIDER", "append_jsonl", "expand_matrix", "run_attempt", "run_matrix"]
