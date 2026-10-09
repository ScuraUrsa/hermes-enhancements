"""Idle gate for backlog work. The backlog may run only when ALL of these hold:

  - quota governor mode is not "idle" (~/.hermes/autonomy/quota.json)
  - Hermes' self-work budget can afford one more video (budget.py can-afford)
  - ytdigest's own daily backlog cap is not spent (spend.jsonl)
  - Filip has no live session: no message from a non-cron/non-kanban session
    in the last N minutes (~/.hermes/state.db and profiles/*/state.db)
  - no task Filip ordered (kanban priority >= 100) is running
  - the VM has CPU and RAM to spare

Every check that cannot read its source passes (missing file = feature not
installed), except the budget, which fails closed when budget.py errors.
"""

from __future__ import annotations

import glob
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

from . import llm

H = Path(os.environ.get("HERMES_REAL_HOME", os.path.expanduser("~"))) / ".hermes"
SELF_SOURCES = {"cron", "kanban"}


def _quota_mode() -> tuple[bool, str]:
    p = H / "autonomy" / "quota.json"
    try:
        mode = json.loads(p.read_text()).get("mode")
    except (OSError, ValueError):
        return True, "quota.json missing"
    return mode != "idle", f"quota mode {mode}"


def _budget(est: float) -> tuple[bool, str]:
    script = H / "scripts" / "budget.py"
    if not script.is_file():
        return True, "budget.py missing"
    r = subprocess.run([sys.executable, str(script), "can-afford", f"{est:.2f}"], capture_output=True, text=True, timeout=120)
    return r.returncode == 0, f"self budget {'ok' if r.returncode == 0 else 'spent'}"


def _own_cap(cfg: dict) -> tuple[bool, str]:
    spent = llm.spent_today(Path(cfg["data_dir"]) / "spend.jsonl", "backlog")
    cap = float(cfg["backlog_daily_cap_usd"])
    return spent + float(cfg["backlog_est_cost_usd"]) <= cap, f"backlog spend today ${spent:.2f}/${cap:.2f}"


def _user_active(quiet_min: int) -> tuple[bool, str]:
    cutoff = time.time() - quiet_min * 60
    dbs = [H / "state.db"] + [Path(p) for p in glob.glob(str(H / "profiles" / "*" / "state.db"))]
    for db in dbs:
        if not db.is_file():
            continue
        try:
            c = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
            row = c.execute(
                "SELECT s.source, MAX(m.timestamp) FROM messages m JOIN sessions s ON s.id=m.session_id "
                "WHERE m.timestamp >= ? AND s.source NOT IN ('cron','kanban') GROUP BY s.source LIMIT 1",
                (cutoff,),
            ).fetchone()
            c.close()
        except sqlite3.Error:
            continue
        if row:
            return False, f"Filip active in a {row[0]} session"
    return True, "no live session"


def _user_tasks() -> tuple[bool, str]:
    db = H / "kanban.db"
    if not db.is_file():
        return True, "kanban.db missing"
    try:
        c = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
        n = c.execute(
            "SELECT COUNT(*) FROM tasks WHERE priority >= 100 AND status IN ('running','in_progress','claimed','doing')"
        ).fetchone()[0]
        c.close()
    except sqlite3.Error:
        return True, "kanban unreadable"
    return n == 0, f"{n} of Filip's tasks running"


def _machine(cfg: dict) -> tuple[bool, str]:
    load = os.getloadavg()[0] / max(1, os.cpu_count() or 1)
    free_mb = None
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                free_mb = int(line.split()[1]) // 1024
    except OSError:
        pass
    ok = load <= cfg["idle_max_load_per_cpu"] and (free_mb is None or free_mb >= cfg["idle_min_free_mem_mb"])
    return ok, f"load/cpu {load:.2f}, free {free_mb} MB"


def check(cfg: dict) -> tuple[bool, list[str]]:
    results = [
        _quota_mode(),
        _own_cap(cfg),
        _user_active(cfg["idle_user_quiet_minutes"]),
        _user_tasks(),
        _machine(cfg),
        _budget(float(cfg["backlog_est_cost_usd"])),
    ]
    return all(ok for ok, _ in results), [("ok  " if ok else "NO  ") + why for ok, why in results]
