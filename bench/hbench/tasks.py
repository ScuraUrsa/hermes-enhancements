"""Task definitions.

A task is a directory under ``tasks/`` with:

* ``task.toml``      metadata, where the code comes from, how to set up and verify
* ``instruction.md`` the prompt every agent gets, written like an issue report

Tasks reference real commits instead of copying code: the workspace is the tree
at ``base_commit`` (default: the parent of ``fix_commit``), and the files listed
in ``hidden_tests`` are restored from ``fix_commit`` only at grading time, so the
agent never sees them.
"""

from __future__ import annotations

import fnmatch
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_EXCLUDES = [".venv/", "node_modules/", "__pycache__/", ".pytest_cache/", ".ruff_cache/"]


@dataclass
class Task:
    id: str
    path: Path
    repo: str
    fix_commit: str
    instruction: str
    base_commit: str | None = None
    category: str = "bugfix"  # bugfix | feature | tests | refactor | infra
    difficulty: str = "medium"  # easy | medium | hard
    tags: list[str] = field(default_factory=list)
    hidden_tests: list[str] = field(default_factory=list)
    setup: str | None = None
    setup_timeout: int = 900
    verify: str = ""
    verify_timeout: int = 900
    regression: str | None = None
    agent_timeout: int = 1800
    env_hint: str | None = None
    excludes: list[str] = field(default_factory=lambda: list(DEFAULT_EXCLUDES))
    # "private" = commit never left Filip's repos; "public" = upstream commit that
    # may be in model training data (contamination risk, report separately).
    visibility: str = "private"

    @property
    def base(self) -> str:
        return self.base_commit or f"{self.fix_commit}^"

    def prompt(self) -> str:
        """The exact text an agent receives."""
        parts = [self.instruction.strip()]
        if self.env_hint:
            parts.append(self.env_hint.strip())
        parts.append(
            "Work only inside the current directory. Do not commit. "
            "When you are done, stop; the change will be graded by hidden tests."
        )
        return "\n\n".join(parts) + "\n"


def load_task(task_dir: Path) -> Task:
    meta = tomllib.loads((task_dir / "task.toml").read_text())
    instruction = (task_dir / "instruction.md").read_text()
    setup = meta.get("setup", {})
    verify = meta.get("verify", {})
    agent = meta.get("agent", {})
    return Task(
        id=meta.get("id", task_dir.name),
        path=task_dir,
        repo=meta["repo"],
        fix_commit=meta["fix_commit"],
        base_commit=meta.get("base_commit"),
        instruction=instruction,
        category=meta.get("category", "bugfix"),
        difficulty=meta.get("difficulty", "medium"),
        tags=list(meta.get("tags", [])),
        hidden_tests=list(meta.get("hidden_tests", [])),
        setup=setup.get("command"),
        setup_timeout=int(setup.get("timeout_sec", 900)),
        verify=verify["command"],
        verify_timeout=int(verify.get("timeout_sec", 900)),
        regression=verify.get("regression"),
        agent_timeout=int(agent.get("timeout_sec", 1800)),
        env_hint=agent.get("env_hint"),
        excludes=list(meta.get("excludes", DEFAULT_EXCLUDES)),
        visibility=meta.get("visibility", "private"),
    )


def load_tasks(root: Path) -> list[Task]:
    return [load_task(d) for d in sorted(root.iterdir()) if (d / "task.toml").is_file()]


def select(tasks: list[Task], patterns: list[str] | None) -> list[Task]:
    """Select by id glob (``crewai-*``) or by tag (``tag:python``)."""
    if not patterns:
        return tasks
    out = []
    for t in tasks:
        for p in patterns:
            if p.startswith("tag:") and p[4:] in t.tags:
                out.append(t)
                break
            if fnmatch.fnmatch(t.id, p):
                out.append(t)
                break
    return out
