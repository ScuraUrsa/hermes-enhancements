"""Workspaces: a fresh git repo holding the task's base tree, with no history.

The agent must not be able to find the fix with ``git log`` or ``git show``, so
the base tree is exported with ``git archive`` into a brand-new repository with
a single commit. Hidden tests and the reference solution are read from the
source repository only when grading (or by the oracle agent).
"""

from __future__ import annotations

import io
import os
import subprocess
import tarfile
from pathlib import Path

from .tasks import Task

GIT_ID = ["-c", "user.name=hbench", "-c", "user.email=hbench@localhost", "-c", "commit.gpgsign=false"]


def git(cwd: Path, *args: str, check: bool = True, binary: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *GIT_ID, *args],
        cwd=cwd,
        check=check,
        capture_output=True,
        text=not binary,
    )


def resolve_repo(task: Task) -> Path:
    """Find a local clone of ``task.repo``, cloning into the cache if needed.

    Lookup order: an absolute path in ``task.repo``; ``$HBENCH_REPOS/<name>``
    (case-insensitive, e.g. ``/home/ubuntu`` on the dev VM where all Hermes
    repos are checked out); ``~/.cache/hbench/repos/<name>`` (cloned from
    GitHub on first use).
    """
    if os.path.isabs(task.repo):
        return Path(task.repo)
    name = task.repo.rsplit("/", 1)[-1]
    for root in filter(None, os.environ.get("HBENCH_REPOS", "").split(os.pathsep)):
        rootp = Path(root).expanduser()
        if not rootp.is_dir():
            continue
        for d in rootp.iterdir():
            if d.name.lower() == name.lower() and (d / ".git").exists():
                return d
    cache = Path(os.environ.get("HBENCH_CACHE", "~/.cache/hbench")).expanduser() / "repos" / name
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--quiet", f"https://github.com/{task.repo}.git", str(cache)], check=True)
    return cache


def ensure_commit(src: Path, commit: str) -> None:
    if git(src, "cat-file", "-e", f"{commit}^{{commit}}", check=False).returncode != 0:
        # Shallow or stale clone: fetch more history.
        git(src, "fetch", "--quiet", "--unshallow", check=False)
        git(src, "fetch", "--quiet", "origin", check=False)
    git(src, "cat-file", "-e", f"{commit}^{{commit}}")


def prepare(task: Task, src: Path, ws: Path) -> str:
    """Create the workspace at ``ws``; returns the workspace's base commit id."""
    ensure_commit(src, task.fix_commit)
    ws.mkdir(parents=True, exist_ok=False)
    archive = git(src, "archive", "--format=tar", task.base, binary=True).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(ws, filter="data")
    git(ws, "init", "--quiet", "-b", "main")
    (ws / ".git" / "info").mkdir(parents=True, exist_ok=True)
    (ws / ".git" / "info" / "exclude").write_text("\n".join(task.excludes) + "\n")
    git(ws, "add", "-A")
    git(ws, "commit", "--quiet", "--no-verify", "-m", f"hbench base for {task.id}")
    return git(ws, "rev-parse", "HEAD").stdout.strip()


def _file_at(src: Path, commit: str, path: str) -> bytes | None:
    r = git(src, "show", f"{commit}:{path}", check=False, binary=True)
    return r.stdout if r.returncode == 0 else None


def restore_from_fix(task: Task, src: Path, ws: Path, paths: list[str]) -> None:
    """Write ``paths`` into the workspace exactly as they are at ``fix_commit``."""
    for p in paths:
        data = _file_at(src, task.fix_commit, p)
        target = ws / p
        if data is None:
            target.unlink(missing_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def fix_files(task: Task, src: Path) -> list[str]:
    """Files the reference fix changed, minus the hidden tests."""
    out = git(src, "diff", "--name-only", task.base, task.fix_commit).stdout.split()
    hidden = set(task.hidden_tests)
    return [p for p in out if p not in hidden]


def diff_stats(ws: Path, base: str, out_patch: Path) -> dict:
    """Stage everything the agent did and record the patch and its size."""
    git(ws, "add", "-A")
    patch = git(ws, "diff", "--cached", base, check=False).stdout
    out_patch.write_text(patch)
    files = added = removed = 0
    for line in git(ws, "diff", "--cached", "--numstat", base, check=False).stdout.splitlines():
        a, r, _ = line.split("\t", 2)
        files += 1
        added += int(a) if a.isdigit() else 0
        removed += int(r) if r.isdigit() else 0
    return {"files_changed": files, "lines_added": added, "lines_removed": removed}
