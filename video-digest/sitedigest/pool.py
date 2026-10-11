"""Several workers on one site without stepping on each other.

A small SQLite queue (<root>/<site>/queue.db) is the coordinator: every lesson is
one row, a worker *claims* a row with a time-limited lease (one transaction, so
two workers never get the same lesson), digests it and marks it done. A worker
that dies just lets its lease run out and the lesson goes back to the pool. No
extra Claude session is needed to coordinate; the database does it.

  sitedigest pool SITE --workers 3 --model claude-code:sonnet --follow --require-vtt

- Readiness: a lesson enters the pool only when its prefetched videos exist (and,
  with --require-vtt, their transcripts too), so a half-synced folder is never
  analysed (this is what made the first run go dry).
- --follow keeps re-reading the map for newly synced lessons until --max-minutes.
- Claude usage limit: the first worker that hits it pauses the whole pool until
  the window resets (read from Claude's message, else --pause-minutes); with --fallback-model the lesson is
  done with that model instead of waiting.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from pathlib import Path

from . import crawl, course, session

LIMIT_WORDS = ("usage limit", "rate limit", "limit reached", "hit your limit", "429", "overloaded", "quota")
RESET_EPOCH = re.compile(r"limit reached\|(\d{10})")
RESET_CLOCK = re.compile(r"resets\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", re.I)


def db_path(cfg: dict, site: str) -> Path:
    return session.site_dir(cfg, site) / "queue.db"


def connect(cfg: dict, site: str) -> sqlite3.Connection:
    db = sqlite3.connect(db_path(cfg, site), timeout=60, isolation_level=None)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS jobs (
        key TEXT PRIMARY KEY, ord INTEGER, status TEXT NOT NULL DEFAULT 'queued',
        owner TEXT, lease_until REAL, attempts INTEGER NOT NULL DEFAULT 0, error TEXT, updated REAL)""")
    db.execute("CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)")
    return db


def ready(cfg: dict, site: str, rec: dict, require_vtt: bool) -> bool:
    """Every local:<path> video of the page exists (and has a .vtt next to it if required)."""
    pdir = crawl.page_dir(cfg, site, rec["key"])
    for v in rec.get("videos") or []:
        if not v.startswith("local:"):
            continue
        f = pdir / v[len("local:"):]
        if not f.is_file():
            return False
        if require_vtt and not list(f.parent.glob(f"{f.stem}*.vtt")):
            return False
    return True


def sync(cfg: dict, site: str, db: sqlite3.Connection, *, require_vtt: bool = False, include=None) -> int:
    """Add lessons that are pending in the map and ready on disk; returns how many were added."""
    m = crawl.load_map(cfg, site) or {"pages": []}
    known = {k for (k,) in db.execute("SELECT key FROM jobs")}
    added = 0
    for rec in course.pending(m):
        if rec["key"] in known or (include and not (include.search(rec["url"]) or include.search(rec.get("section") or ""))):
            continue
        if ready(cfg, site, rec, require_vtt):
            db.execute("INSERT OR IGNORE INTO jobs(key, ord, updated) VALUES (?,?,?)", (rec["key"], rec.get("order") or 0, time.time()))
            added += 1
    return added


def claim(db: sqlite3.Connection, owner: str, lease_sec: float = 1800) -> str | None:
    now = time.time()
    db.execute("BEGIN IMMEDIATE")
    try:
        row = db.execute("""SELECT key FROM jobs WHERE status='queued' OR (status='leased' AND lease_until < ?)
                            ORDER BY ord LIMIT 1""", (now,)).fetchone()
        if not row:
            db.execute("COMMIT")
            return None
        db.execute("UPDATE jobs SET status='leased', owner=?, lease_until=?, attempts=attempts+1, updated=? WHERE key=?",
                   (owner, now + lease_sec, now, row[0]))
        db.execute("COMMIT")
        return row[0]
    except Exception:
        db.execute("ROLLBACK")
        raise


def finish(db: sqlite3.Connection, key: str, status: str, error: str | None = None) -> None:
    db.execute("UPDATE jobs SET status=?, error=?, owner=NULL, lease_until=NULL, updated=? WHERE key=?",
               (status, error, time.time(), key))


def paused_until(db: sqlite3.Connection) -> float:
    row = db.execute("SELECT v FROM meta WHERE k='paused_until'").fetchone()
    return float(row[0]) if row else 0.0


def pause(db: sqlite3.Connection, seconds: float) -> None:
    db.execute("INSERT INTO meta(k, v) VALUES('paused_until', ?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
               (str(time.time() + seconds),))


def stats(cfg: dict, site: str) -> dict:
    db = connect(cfg, site)
    out = dict(db.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status").fetchall())
    out["paused_until"] = paused_until(db) or None
    return out


def is_limit(error: str | None) -> bool:
    e = (error or "").lower()
    return any(w in e for w in LIMIT_WORDS)


def limit_wait(error: str | None, default_sec: float, now: float | None = None) -> float:
    """Seconds until the Claude limit in `error` resets (plus a 2 min margin), else `default_sec`.

    Understands "usage limit reached|<epoch>" and "... resets 3pm" / "resets 11:50" (local time)."""
    now = time.time() if now is None else now
    e = error or ""
    m = RESET_EPOCH.search(e)
    if m:
        at = float(m.group(1))
    else:
        m = RESET_CLOCK.search(e)
        if not m:
            return default_sec
        h, mi, ap = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or "").lower()
        if ap == "pm" and h < 12:
            h += 12
        elif ap == "am" and h == 12:
            h = 0
        t = time.localtime(now)
        at = time.mktime((t.tm_year, t.tm_mon, t.tm_mday, h, mi, 0, 0, 0, -1))
        if at <= now:
            at += 86400
    wait = at - now + 120
    return wait if 0 < wait <= 6 * 3600 else default_sec


def worker(cfg: dict, site: str, n: int, *, model: str | None, fallback_model: str | None, deadline: float,
           follow: bool, require_vtt: bool, include, pause_minutes: float, write_notion: bool, log) -> dict:
    from . import lesson

    owner = f"{os.uname().nodename if hasattr(os, 'uname') else 'pc'}:{os.getpid()}:w{n}"
    db = connect(cfg, site)
    done = failed = 0
    while time.time() < deadline:
        wait = paused_until(db) - time.time()
        if wait > 0:
            if not fallback_model:
                time.sleep(min(wait, 60))
                continue
        if n == 0:  # one worker keeps the pool topped up from the map
            sync(cfg, site, db, require_vtt=require_vtt, include=include)
        key = claim(db, owner)
        if not key:
            if not follow:
                break
            time.sleep(30)
            continue
        rec = next((p for p in (crawl.load_map(cfg, site) or {"pages": []})["pages"] if p["key"] == key), None)
        if rec is None:
            finish(db, key, "failed", "not in map")
            continue
        use = fallback_model if (paused_until(db) > time.time() and fallback_model) else model
        try:
            res = lesson.digest(cfg, site, rec, model=use, write_notion=write_notion, tag="manual",
                                log=lambda m, n=n: log(f"[w{n}] {m}"))
        except Exception as exc:
            err = f"{type(exc).__name__}: {str(exc)[:400]}"
            if is_limit(err):
                sec = limit_wait(err, pause_minutes * 60)
                log(f"[w{n}] usage limit hit; pausing the pool {sec / 60:.0f} min")
                pause(db, sec)
                finish(db, key, "queued")  # back to the pool, not a failure
                continue
            res = {"key": key, "status": "failed", "error": err}
        crawl.update_pages(cfg, site, {key: res})
        finish(db, key, "done" if res["status"] in ("done", "partial") else "failed", res.get("error"))
        done += res["status"] in ("done", "partial")
        failed += res["status"] == "failed"
    return {"worker": n, "done": done, "failed": failed}


def run(cfg: dict, site: str, *, workers: int = 3, model: str | None = None, fallback_model: str | None = None,
        max_minutes: float = 600, follow: bool = False, require_vtt: bool = False, include: str | None = None,
        pause_minutes: float = 30, write_notion: bool = True, log=print) -> list[dict]:
    """Start `workers` processes on the site's pool; returns their tallies."""
    import multiprocessing as mp

    rx = re.compile(include) if include else None
    db = connect(cfg, site)
    # leases of a pool that was killed come back at once
    db.execute("UPDATE jobs SET status='queued', owner=NULL WHERE status='leased'")
    added = sync(cfg, site, db, require_vtt=require_vtt, include=rx)
    log(f"pool '{site}': {added} lessons added, {workers} workers, model {model or 'routing default'}")
    deadline = time.time() + max_minutes * 60
    kw = dict(model=model, fallback_model=fallback_model, deadline=deadline, follow=follow, require_vtt=require_vtt,
              include=rx, pause_minutes=pause_minutes, write_notion=write_notion, log=log)
    if workers <= 1:
        return [worker(cfg, site, 0, **kw)]
    fork = hasattr(os, "fork")
    ctx = mp.get_context("fork" if fork else "spawn")
    if not fork:  # spawn pickles arguments: use the module-level logger
        kw["log"] = _stderr
    out = ctx.Queue()
    procs = [ctx.Process(target=_child, args=(out, cfg, site, n, kw), daemon=False) for n in range(workers)]
    for p in procs:
        p.start()
    results = [out.get() for _ in procs]
    for p in procs:
        p.join()
    return sorted(results, key=lambda r: r["worker"])


def _child(out, cfg, site, n, kw) -> None:
    try:
        out.put(worker(cfg, site, n, **kw))
    except Exception as exc:  # report, never hang the parent
        out.put({"worker": n, "done": 0, "failed": 0, "error": f"{type(exc).__name__}: {exc}"})


def _stderr(msg: str) -> None:
    import sys

    print(msg, file=sys.stderr, flush=True)
