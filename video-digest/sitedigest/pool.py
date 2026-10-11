"""Several workers on one site without stepping on each other.

A small SQLite queue (<root>/<site>/queue.db) is the coordinator: every lesson is
one row, a worker *claims* a row with a time-limited lease (one transaction, so
two workers never get the same lesson), keeps the lease alive while it works,
digests the lesson and marks it done. A worker that dies just lets its lease run
out and the lesson goes back to the pool; after MAX_ATTEMPTS it is marked failed
instead of crashing worker after worker. No extra Claude session is needed to
coordinate; the database does it.

  sitedigest pool SITE --workers 3 --model claude-code:sonnet --follow --require-vtt

- One pool at a time: the pool holds the same lock as `digest SITE` and the cron
  `worker`, so those never digest a lesson the pool is working on.
- Readiness: a lesson enters the pool only when its prefetched videos exist (and,
  with --require-vtt, their transcripts too), so a half-synced folder is never
  analysed (this is what made the first run go dry).
- --follow keeps re-reading the map for newly synced lessons until --max-minutes.
- Re-runs: a lesson whose map digest status is 'requeued' (course-harvest's
  requeue.py) goes back into the pool once.
- Claude usage limit (ytdigest.llm.LimitError, decided on the CLI's own message):
  the first worker that hits it pauses the whole pool until the window resets
  (read from Claude's message, else --pause-minutes); with --fallback-model the
  lesson is done with that model instead of waiting.
"""

from __future__ import annotations

import os
import re
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from ytdigest import llm

from . import crawl, course, media, session

LEASE_SEC = 1800       # renewed every HEARTBEAT_SEC while the worker is alive
HEARTBEAT_SEC = 300
MAX_ATTEMPTS = 3       # claims that ended without a result (crash, kill) before a lesson is given up
RESET_EPOCH = re.compile(r"limit reached\|(\d{10})")
MONTHS = "jan feb mar apr may jun jul aug sep oct nov dec".split()
RESET_CLOCK = re.compile(r"resets\s+(?:on\s+)?(?:(?P<mon>[A-Za-z]{3})[a-z]*\.?\s+(?P<day>\d{1,2}),?\s+)?(?:at\s+)?"
                         r"(?P<h>\d{1,2})(?::(?P<m>\d{2}))?\s*(?P<ap>am|pm)?(?:\s*\((?P<tz>[A-Za-z_]+/[A-Za-z_/]+|UTC)\))?", re.I)


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
    """Every local:<path> video of the page exists (and has a caption file next to it if required)."""
    pdir = crawl.page_dir(cfg, site, rec["key"])
    for v in rec.get("videos") or []:
        if not v.startswith("local:"):
            continue
        f = pdir / v[len("local:"):]
        if not f.is_file():
            return False
        if require_vtt and not media.captions_for(f):
            return False
    return True


def sync(cfg: dict, site: str, db: sqlite3.Connection, *, require_vtt: bool = False, include=None) -> int:
    """Add lessons that are pending in the map and ready on disk; returns how many were added."""
    m = crawl.load_map(cfg, site) or {"pages": []}
    known = dict(db.execute("SELECT key, status FROM jobs").fetchall())
    added = 0
    for rec in course.pending(m):
        if include and not (include.search(rec["url"]) or include.search(rec.get("section") or "")):
            continue
        st = known.get(rec["key"])
        # a finished lesson comes back only when it was sent back on purpose (digest status
        # 'requeued', e.g. a mind map was added); a failed one stays failed, no retry loop
        if st is not None and not (st in ("done", "failed") and (rec.get("digest") or {}).get("status") == "requeued"):
            continue
        if ready(cfg, site, rec, require_vtt):
            db.execute("""INSERT INTO jobs(key, ord, updated) VALUES (?,?,?) ON CONFLICT(key) DO UPDATE SET
                          status='queued', owner=NULL, lease_until=NULL, attempts=0, error=NULL, updated=excluded.updated""",
                       (rec["key"], rec.get("order") or 0, time.time()))
            added += 1
    return added


def claim(db: sqlite3.Connection, owner: str, lease_sec: float = LEASE_SEC) -> str | None:
    now = time.time()
    db.execute("BEGIN IMMEDIATE")
    try:
        # a lease that ran out means its worker died; after MAX_ATTEMPTS the lesson is the problem
        db.execute("""UPDATE jobs SET status='failed', owner=NULL, lease_until=NULL, updated=?,
                      error=COALESCE(error, 'worker died ' || attempts || ' times on this lesson')
                      WHERE status='leased' AND lease_until < ? AND attempts >= ?""", (now, now, MAX_ATTEMPTS))
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


def renew(db: sqlite3.Connection, key: str, owner: str, lease_sec: float = LEASE_SEC) -> bool:
    cur = db.execute("UPDATE jobs SET lease_until=? WHERE key=? AND owner=? AND status='leased'",
                     (time.time() + lease_sec, key, owner))
    return cur.rowcount == 1


def owns(db: sqlite3.Connection, key: str, owner: str) -> bool:
    return db.execute("SELECT 1 FROM jobs WHERE key=? AND owner=? AND status='leased'", (key, owner)).fetchone() is not None


def finish(db: sqlite3.Connection, key: str, status: str, error: str | None = None, *, owner: str | None = None,
           refund: bool = False) -> bool:
    """Close a claim. With `owner`, only if that worker still holds it (False otherwise).
    `refund` gives back the attempt (a usage-limit pause is not the lesson's fault)."""
    sql = ("UPDATE jobs SET status=?, error=?, owner=NULL, lease_until=NULL, updated=?"
           + (", attempts=MAX(attempts-1, 0)" if refund else "") + " WHERE key=?")
    args: list = [status, error, time.time(), key]
    if owner is not None:
        sql += " AND owner=?"
        args.append(owner)
    return db.execute(sql, args).rowcount == 1


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
    """Text form of llm.LimitError (for errors that crossed a process or a log)."""
    return bool(llm.CLAUDE_LIMIT.search(error or ""))


def limit_wait(error: str | None, default_sec: float, now: float | None = None) -> float:
    """Seconds until the Claude limit in `error` resets (plus a 2 min margin), else `default_sec`.

    Understands "usage limit reached|<epoch>", "resets 3pm (Europe/Warsaw)", "resets 11:50"
    and "resets Oct 14, 3pm" (a weekly limit). Without a zone the machine's local time is used."""
    now = time.time() if now is None else now
    e = error or ""
    cap = 6 * 3600
    m = RESET_EPOCH.search(e)
    if m:
        at = float(m.group(1))
    else:
        m = RESET_CLOCK.search(e)
        if not m:
            return default_sec
        tz = None
        if m["tz"]:
            try:
                from zoneinfo import ZoneInfo

                tz = ZoneInfo(m["tz"])
            except Exception:  # unknown zone name: fall back to local time
                tz = None
        h, mi, ap = int(m["h"]), int(m["m"] or 0), (m["ap"] or "").lower()
        if h > 23 or mi > 59:
            return default_sec
        if ap == "pm" and h < 12:
            h += 12
        elif ap == "am" and h == 12:
            h = 0
        base = datetime.fromtimestamp(now, tz) if tz else datetime.fromtimestamp(now)
        try:
            if m["mon"] and m["mon"].lower()[:3] in MONTHS:
                cap = 8 * 86400
                t = base.replace(month=MONTHS.index(m["mon"].lower()[:3]) + 1, day=int(m["day"]), hour=h, minute=mi,
                                 second=0, microsecond=0)
                if t.timestamp() <= now:
                    t = t.replace(year=t.year + 1)
            else:
                t = base.replace(hour=h, minute=mi, second=0, microsecond=0)
                if t.timestamp() <= now:
                    t += timedelta(days=1)
        except ValueError:  # e.g. Feb 30
            return default_sec
        at = t.timestamp()
    wait = at - now + 120
    return wait if 0 < wait <= cap else default_sec


def _heartbeat(cfg: dict, site: str, key: str, owner: str, stop: threading.Event) -> None:
    db = connect(cfg, site)  # sqlite connections are per thread
    try:
        while not stop.wait(HEARTBEAT_SEC):
            renew(db, key, owner)
    finally:
        db.close()


def worker(cfg: dict, site: str, n: int, *, model: str | None, fallback_model: str | None, deadline: float,
           follow: bool, require_vtt: bool, include, pause_minutes: float, write_notion: bool, log) -> dict:
    from . import lesson

    owner = f"{os.uname().nodename if hasattr(os, 'uname') else 'pc'}:{os.getpid()}:w{n}"
    db = connect(cfg, site)
    done = failed = 0
    while time.time() < deadline:
        wait = paused_until(db) - time.time()
        if wait > 0 and not fallback_model:
            time.sleep(max(1.0, min(wait, 60, deadline - time.time())))
            continue
        if n == 0:  # one worker keeps the pool topped up from the map
            try:
                sync(cfg, site, db, require_vtt=require_vtt, include=include)
            except Exception as exc:  # e.g. map.json being replaced on Windows: next round
                log(f"[w{n}] sync skipped: {type(exc).__name__}: {str(exc)[:160]}")
        key = claim(db, owner)
        if not key:
            if not follow:
                break
            time.sleep(max(1.0, min(30, deadline - time.time())))
            continue
        rec = next((p for p in (crawl.load_map(cfg, site) or {"pages": []})["pages"] if p["key"] == key), None)
        if rec is None:
            finish(db, key, "failed", "not in map", owner=owner)
            continue
        use = fallback_model if (paused_until(db) > time.time() and fallback_model) else model
        stop = threading.Event()
        beat = threading.Thread(target=_heartbeat, args=(cfg, site, key, owner, stop), daemon=True)
        beat.start()
        try:
            res = lesson.digest(cfg, site, rec, model=use, write_notion=write_notion, tag="manual",
                                log=lambda m, n=n: log(f"[w{n}] {m}"))
        except llm.LimitError as exc:
            err = f"{type(exc).__name__}: {str(exc)[:400]}"
            sec = limit_wait(err, pause_minutes * 60)
            log(f"[w{n}] Claude usage limit; pausing the pool {sec / 60:.0f} min")
            pause(db, sec)
            finish(db, key, "queued", owner=owner, refund=True)  # back to the pool, not a failure
            continue
        except Exception as exc:
            res = {"key": key, "status": "failed", "error": f"{type(exc).__name__}: {str(exc)[:400]}"}
        finally:
            stop.set()
        status = "done" if res["status"] in ("done", "partial") else "failed"
        try:
            if not owns(db, key, owner):  # the lease was lost (pool restarted): the new holder records it
                log(f"[w{n}] {key}: lease lost, result not recorded")
                continue
            crawl.update_pages(cfg, site, {key: res})
            finish(db, key, status, res.get("error"), owner=owner)
        except Exception as exc:  # keep the worker alive; the lease runs out and the lesson is retried
            log(f"[w{n}] {key}: could not record the result: {type(exc).__name__}: {str(exc)[:160]}")
            continue
        done += status == "done"
        failed += status == "failed"
    return {"worker": n, "done": done, "failed": failed}


def run(cfg: dict, site: str, *, workers: int = 3, model: str | None = None, fallback_model: str | None = None,
        max_minutes: float = 600, follow: bool = False, require_vtt: bool = False, include: str | None = None,
        pause_minutes: float = 30, write_notion: bool = True, log=print) -> list[dict]:
    """Start `workers` processes on the site's pool; returns their tallies.

    The caller holds the sitedigest worker lock (cli.cmd_pool), so this is the only pool
    and nothing else digests this site meanwhile."""
    import multiprocessing as mp
    import queue as _queue

    rx = re.compile(include) if include else None
    db = connect(cfg, site)
    # we are the only pool: leases left in the table belong to a pool that was killed
    db.execute("UPDATE jobs SET status='queued', owner=NULL, lease_until=NULL WHERE status='leased'")
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
    results: dict[int, dict] = {}
    while len(results) < len(procs):
        try:
            r = out.get(timeout=5)
            results[r["worker"]] = r
            continue
        except _queue.Empty:
            pass
        for n, p in enumerate(procs):  # a child killed outright (OOM, signal) never reports
            if n in results or p.is_alive():
                continue
            try:  # its last words may still be in the pipe
                r = out.get(timeout=1)
                results[r["worker"]] = r
            except _queue.Empty:
                results[n] = {"worker": n, "done": 0, "failed": 0, "error": f"worker exited with code {p.exitcode}"}
                log(f"[w{n}] worker exited with code {p.exitcode} without a report")
    for p in procs:
        p.join(timeout=10)
    return sorted(results.values(), key=lambda r: r["worker"])


def _child(out, cfg, site, n, kw) -> None:
    try:
        out.put(worker(cfg, site, n, **kw))
    except Exception as exc:  # report, never hang the parent
        out.put({"worker": n, "done": 0, "failed": 0, "error": f"{type(exc).__name__}: {exc}"})


def _stderr(msg: str) -> None:
    import sys

    print(msg, file=sys.stderr, flush=True)
