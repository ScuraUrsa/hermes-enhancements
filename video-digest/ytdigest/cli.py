"""ytdigest command line.

  ytdigest run <url> [--no-notion] [--analyzer frames|gemini_url]   one video, now
  ytdigest add <url>... [--now]                                     queue (backlog, or --now = priority 100)
  ytdigest add --file ids.txt --account A --playlist P              queue a list (one URL/id per line)
  ytdigest worker [--idle-only] [--max-videos N] [--max-minutes M]  drain the queue
  ytdigest backlog-sync [--account fjkazmierczak]                  queue all playlists
  ytdigest compare --refs A,B --file ids.txt [--notion-parent ID]   same videos, several models
  ytdigest discover [--days 730] [--ids-file wl.txt] [--queue]      recent uploads of followed/saved channels
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

from . import backlog, compare, config, discover, fetch, gate, llm, pipeline
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
    urls = list(a.urls)
    if a.file:
        # one URL or video id per line; blanks and # comments ignored (e.g. a Watch later export)
        lines = Path(a.file).read_text(encoding="utf-8").splitlines()
        urls += [ln.strip() for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]
    if a.now:
        prio = USER_PRIORITY
    elif a.file or a.backlog:
        prio = BACKLOG_PRIORITY
    else:
        prio = BACKLOG_PRIORITY + 20
    added = known = bad = 0
    for u in urls:
        try:
            vid = fetch.video_id(u)
        except ValueError:
            bad += 1
            print(f"skipped (not a video): {u[:80]}")
            continue
        new = q.add(vid, fetch.watch_url(vid), priority=prio, account=a.account or "ręcznie", playlist=a.playlist)
        added, known = added + new, known + (not new)
        if not a.file:
            print(f"{'queued' if new else 'already known'}: {vid}")
    if a.file:
        print(f"{a.file}: {added} queued, {known} already known, {bad} skipped")
    return 0


def cmd_compare(cfg, a) -> int:
    urls = list(a.urls)
    if a.file:
        lines = Path(a.file).read_text(encoding="utf-8").splitlines()
        urls += [ln.split()[0] for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]
    refs = [r.strip() for r in a.refs.split(",") if r.strip()]
    res = compare.run(cfg, urls, refs, log=lambda m: print(m, flush=True))
    print(f"results: {res['dir']}/results.json and comparison.md")
    if a.notion_parent:
        print("notion:", compare.publish_notion(res, refs, a.notion_parent, a.title))
    return 0


def cmd_discover(cfg, a) -> int:
    out = Path(a.out or Path(cfg["data_dir"]) / f"discover_{a.account}_{a.days}d.tsv")
    res = discover.run(cfg, a.account, a.days, out, id_files=a.ids_file or [], include_subs=not a.no_subs,
                       skip_shorts=a.skip_shorts, min_seconds=a.min_seconds, max_per_channel=a.max_per_channel,
                       log=lambda m: print(m, flush=True))
    if a.queue:
        q = _q(cfg)
        n = sum(q.add(r["video_id"], fetch.watch_url(r["video_id"]), title=r["title"], account=a.account,
                      playlist=f"Kanał: {r['channel']}", priority=discover.DISCOVER_PRIORITY) for r in res["rows"])
        print(f"queued {n} new videos at priority {discover.DISCOVER_PRIORITY} (after all other backlog)")
    print(json.dumps(res["summary"], ensure_ascii=False))
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
    ad.add_argument("urls", nargs="*")
    ad.add_argument("--now", action="store_true", help="priority 100: next worker run takes it, no idle gate")
    ad.add_argument("--file", help="read URLs / video ids from a file, one per line (queued as backlog)")
    ad.add_argument("--account", help="account the videos came from, e.g. fjkazmierczak")
    ad.add_argument("--playlist", help="playlist name shown in Notion, e.g. 'Do obejrzenia'")
    ad.add_argument("--backlog", action="store_true", help="queue at backlog priority (idle gate)")
    ad.set_defaults(fn=cmd_add)
    cp = sub.add_parser("compare", help="same videos through several models; tokens, time, output")
    cp.add_argument("urls", nargs="*")
    cp.add_argument("--file", help="one URL / video id per line")
    cp.add_argument("--refs", default="claude-code:sonnet,claude-code:haiku")
    cp.add_argument("--notion-parent", help="Notion page id to put the comparison page under")
    cp.add_argument("--title", default="Porównanie modeli: Sonnet vs Haiku")
    cp.set_defaults(fn=cmd_compare)
    ds = sub.add_parser("discover", help="recent videos from every channel you save or subscribe to")
    ds.add_argument("--account", default="fjkazmierczak")
    ds.add_argument("--days", type=int, default=730)
    ds.add_argument("--ids-file", action="append", help="extra saved ids (e.g. the Watch later export); repeatable")
    ds.add_argument("--no-subs", action="store_true", help="leave subscriptions out")
    ds.add_argument("--skip-shorts", action="store_true", help="drop videos of 60 s or less")
    ds.add_argument("--min-seconds", type=int, default=0, help="drop videos shorter than this (e.g. 180)")
    ds.add_argument("--max-per-channel", type=int, default=0, help="keep only the newest N per channel")
    ds.add_argument("--out", help="TSV path (default data_dir/discover_<account>_<days>d.tsv)")
    ds.add_argument("--queue", action="store_true", help="also queue them, below all other backlog")
    ds.set_defaults(fn=cmd_discover)
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
