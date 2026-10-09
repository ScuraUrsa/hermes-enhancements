"""ytdigest command line.

  ytdigest run <url> [--no-notion] [--analyzer frames|gemini_url]   one video, now
  ytdigest add <url>... [--now]                                     queue (backlog, or --now = priority 100)
  ytdigest worker [--idle-only] [--max-videos N] [--max-minutes M]  drain the queue
  ytdigest backlog-sync [--account koalamis6]                       queue all playlists
  ytdigest gate                                                     show the idle checks
  ytdigest status                                                   queue counts and spend
  ytdigest serve --host 127.0.0.1 --port 8765                       one-click endpoint
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
import time
from pathlib import Path

from . import backlog, config, fetch, gate, llm, pipeline
from .queue import BACKLOG_PRIORITY, USER_PRIORITY, Queue


def _q(cfg: dict) -> Queue:
    return Queue(Path(cfg["data_dir"]) / "queue.db")


def notify_ha(cfg: dict, res: dict) -> None:
    """Push a phone notification through Home Assistant when configured."""
    svc, url, tok = cfg.get("notify_ha_service"), os.environ.get("HASS_URL"), os.environ.get("HASS_TOKEN")
    if not (svc and url and tok):
        return
    import requests

    domain, _, name = svc.partition(".")
    ok = res.get("status") in ("done", "artistic")
    msg = (res.get("one_line") or res.get("title") or res["video_id"]) if ok else f"Błąd: {res.get('error', '')[:200]}"
    try:
        requests.post(f"{url.rstrip('/')}/api/services/{domain}/{name}",
                      headers={"Authorization": f"Bearer {tok}"},
                      json={"title": "Hermes: raport z filmu" if ok else "Hermes: nie udało się",
                            "message": msg, "data": {"url": res.get("notion_url") or "", "clickAction": res.get("notion_url") or ""}},
                      timeout=15)
    except Exception:
        pass


def cmd_run(cfg, a) -> int:
    res = pipeline.safe_process(a.url, cfg, write_notion=not a.no_notion, force_analyzer=a.analyzer,
                                tag="manual", log=lambda m: print(m, file=sys.stderr))
    q = _q(cfg)
    if res["status"] != "failed":
        q.add(res["video_id"], fetch.watch_url(res["video_id"]), title=res.get("title"), priority=USER_PRIORITY, account="ręcznie")
        q.db.execute("UPDATE videos SET status=?, notion_url=?, cost_usd=? WHERE video_id=?",
                     (res["status"], res.get("notion_url"), res.get("cost_usd", 0), res["video_id"]))
        q.db.commit()
    if a.json:
        print(json.dumps({k: v for k, v in res.items() if k != "trace"}, ensure_ascii=False, indent=1))
    elif res["status"] == "failed":
        print(f"FAILED {res['video_id']}: {res['error']}\n{res.get('trace', '')}", file=sys.stderr)
    else:
        print(res["report_md"])
    notify_ha(cfg, res)
    return 0 if res["status"] != "failed" else 1


def cmd_add(cfg, a) -> int:
    q = _q(cfg)
    for u in a.urls:
        vid = fetch.video_id(u)
        new = q.add(vid, fetch.watch_url(vid), priority=USER_PRIORITY if a.now else BACKLOG_PRIORITY + 20, account="ręcznie")
        print(f"{'queued' if new else 'already known'}: {vid}")
    return 0


def cmd_worker(cfg, a) -> int:
    lock_path = Path(cfg["data_dir"]) / "worker.lock"
    lock = lock_path.open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("another worker is running")
        return 0
    q = _q(cfg)
    q.release_stuck()
    deadline = time.time() + a.max_minutes * 60
    done = 0
    while done < a.max_videos and time.time() < deadline:
        # Filip's own requests never wait for the gate.
        row = q.next(min_priority=USER_PRIORITY)
        tag = "manual"
        if row is None:
            if a.only_user:
                break
            if a.idle_only:
                ok, why = gate.check(cfg)
                if not ok:
                    print("gate closed:\n  " + "\n  ".join(why))
                    break
            row = q.next()
            tag = "backlog"
        if row is None:
            print("queue empty")
            break
        res = pipeline.safe_process(row["url"], cfg, account=row["account"],
                                    playlists=json.loads(row["playlists"] or "[]"), tag=tag)
        q.finish(row["video_id"], res)
        print(f"{row['video_id']}: {res['status']} ${res.get('cost_usd', 0):.4f} {res.get('notion_url') or res.get('error', '')}")
        if tag == "manual":
            notify_ha(cfg, res)
        done += 1
    return 0


def cmd_backlog(cfg, a) -> int:
    backlog.sync(cfg, _q(cfg), a.account or None)
    return 0


def cmd_gate(cfg, a) -> int:
    ok, why = gate.check(cfg)
    print(("OPEN" if ok else "CLOSED") + "\n  " + "\n  ".join(why))
    return 0 if ok else 1


def cmd_status(cfg, a) -> int:
    print(json.dumps({
        "queue": _q(cfg).stats(),
        "backlog_spend_today_usd": llm.spent_today(Path(cfg["data_dir"]) / "spend.jsonl", "backlog"),
        "manual_spend_today_usd": llm.spent_today(Path(cfg["data_dir"]) / "spend.jsonl", "manual"),
    }, indent=1, ensure_ascii=False))
    return 0


def cmd_serve(cfg, a) -> int:
    from . import server

    server.serve(cfg, Path(cfg["data_dir"]) / "queue.db", a.host, a.port, notify=lambda r: notify_ha(cfg, r))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ytdigest", description="YouTube video -> Notion report")
    p.add_argument("--config")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="process one video now")
    r.add_argument("url")
    r.add_argument("--no-notion", action="store_true")
    r.add_argument("--analyzer", choices=["gemini_url", "frames"])
    r.add_argument("--json", action="store_true")
    r.set_defaults(fn=cmd_run)
    ad = sub.add_parser("add", help="queue videos")
    ad.add_argument("urls", nargs="+")
    ad.add_argument("--now", action="store_true", help="priority 100: next worker run takes it, no idle gate")
    ad.set_defaults(fn=cmd_add)
    w = sub.add_parser("worker", help="process queued videos")
    w.add_argument("--idle-only", action="store_true", help="backlog only when the idle gate is open")
    w.add_argument("--only-user", action="store_true", help="only Filip's priority-100 items")
    w.add_argument("--max-videos", type=int, default=5)
    w.add_argument("--max-minutes", type=int, default=25)
    w.set_defaults(fn=cmd_worker)
    b = sub.add_parser("backlog-sync", help="queue videos from all accounts' playlists")
    b.add_argument("--account", action="append")
    b.set_defaults(fn=cmd_backlog)
    sub.add_parser("gate").set_defaults(fn=cmd_gate)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    s = sub.add_parser("serve", help="HTTP endpoint for one-click use")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8765)
    s.set_defaults(fn=cmd_serve)
    a = p.parse_args(argv)
    cfg = config.load(a.config)
    return a.fn(cfg, a)


if __name__ == "__main__":
    sys.exit(main())
