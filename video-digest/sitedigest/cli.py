"""sitedigest command line.

  sitedigest login URL [--site S] [--auto]           log in once (visible browser), session saved
  sitedigest import-cookies cookies.txt --site S     or reuse cookies exported from your browser
  sitedigest map URL [--site S] [--max-pages N]      map the site (resumable)
  sitedigest outline SITE                            modules, lessons, videos, files found
  sitedigest fetch SITE [--limit N] [--include RE]   download videos and files now (where the login lives)
  sitedigest digest SITE [--limit N] [--page KEY]    analyse lessons now (text, files, speech, picture)
  sitedigest pool SITE --workers 3 [--follow]        parallel digest from a shared queue (no collisions)
  sitedigest course SITE                             course overview from the lesson reports
  sitedigest run URL [--limit N]                     map + digest + overview in one go
  sitedigest worker [--idle-only]                    all sites, only while Hermes is idle (cron)
  sitedigest status                                  per site: pages, digested, cost
  sitedigest notion-setup --parent PAGE_ID           create the "Kursy: lekcje" database
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from . import config, course, crawl, notion_out, session


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _site(a, url: str | None = None) -> str:
    return a.site or session.site_name(url or a.url)


def _lock(cfg: dict):
    fh = open(Path(cfg["site"]["root"]) / ".worker.lock", "w")
    try:
        try:
            import fcntl

            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except ImportError:  # Windows PC: fetch/map run there too
            import msvcrt

            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
    except (BlockingIOError, OSError):
        _log("another sitedigest digest/worker is running")
        raise SystemExit(0)
    return fh


def cmd_login(cfg, a) -> int:
    session.login(cfg, a.url, _site(a), auto=a.auto, log=_log)
    return 0


def cmd_import(cfg, a) -> int:
    site = a.site or session.site_name(a.url or "")
    n = session.import_cookies(cfg, site, Path(a.file))
    _log(f"{n} cookies imported for '{site}'")
    return 0


def cmd_map(cfg, a) -> int:
    site = _site(a)
    if not session.load_state(cfg, site):
        _log(f"no session for '{site}' yet: run `sitedigest login {a.url}` or import-cookies first (mapping as a guest)")
    m = crawl.run(cfg, site, a.url, include=a.include, exclude=a.exclude, hosts=a.host, max_pages=a.max_pages,
                  max_depth=a.max_depth, refresh=a.refresh, headless=not a.show, log=_log)
    print(crawl.outline(m))
    return 0


def cmd_outline(cfg, a) -> int:
    m = crawl.load_map(cfg, a.site)
    if not m:
        _log(f"no map for '{a.site}'")
        return 1
    text = crawl.outline(m)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


def cmd_digest(cfg, a) -> int:
    _lk = _lock(cfg)
    res = course.digest_site(cfg, a.site, keys=a.page, limit=a.limit, model=a.model, write_notion=not a.no_notion,
                             redo=a.redo, include_index=a.all, log=_log)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if all(r["status"] != "failed" for r in res) else 1


def cmd_fetch(cfg, a) -> int:
    """Download only, no models: for sites with expiring player links, run this on the PC
    that holds the login, sync <root>/<site>/ to the VM, then digest there."""
    import re

    from . import lesson

    m = crawl.load_map(cfg, a.site)
    if not m:
        _log(f"no map for '{a.site}'")
        return 1
    rx = re.compile(a.include) if a.include else None
    todo = [p for p in course.pending(m) if not p.get("fetched") or a.redo]
    todo = [p for p in todo if not rx or rx.search(p["url"]) or rx.search(p.get("section") or "")][: a.limit or None]
    cookies = str(session.cookies_path(cfg, a.site))

    def one(rec):
        res = lesson.fetch_media(cfg, a.site, rec, cookies=cookies, log=_log)
        rec["fetched"] = res
        crawl.save_map(cfg, a.site, m)
        return res

    res = crawl.fetch_pages(cfg, a.site, todo, one, headless=not a.show, log=_log)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


def cmd_pool(cfg, a) -> int:
    from . import pool

    if a.stats:
        print(json.dumps(pool.stats(cfg, a.site), indent=1))
        return 0
    res = pool.run(cfg, a.site, workers=a.workers, model=a.model, fallback_model=a.fallback_model,
                   max_minutes=a.max_minutes, follow=a.follow, require_vtt=a.require_vtt, include=a.include,
                   pause_minutes=a.pause_minutes, write_notion=not a.no_notion, log=_log)
    print(json.dumps({"workers": res, "queue": pool.stats(cfg, a.site)}, indent=1))
    return 0


def cmd_course(cfg, a) -> int:
    c = course.overview(cfg, a.site, model=a.model, title=a.title, write_notion=not a.no_notion, log=_log)
    print(json.dumps({"title": c["title"], "notion_url": c.get("notion_url"), "one_line": c["report"].get("one_line")},
                     ensure_ascii=False, indent=1))
    return 0


def cmd_run(cfg, a) -> int:
    site = _site(a)
    crawl.run(cfg, site, a.url, include=a.include, exclude=a.exclude, max_pages=a.max_pages, log=_log)
    _lk = _lock(cfg)
    res = course.digest_site(cfg, site, limit=a.limit, model=a.model, write_notion=not a.no_notion, log=_log)
    if any(r["status"] in ("done", "partial") for r in res):
        course.overview(cfg, site, model=a.model, write_notion=not a.no_notion, log=_log)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


def cmd_worker(cfg, a) -> int:
    """Hermes cron: lessons of every mapped site, oldest site first, one at a time,
    re-checking the idle gate before each lesson (same gate as the YouTube backlog)."""
    _lk = _lock(cfg)
    deadline = time.time() + a.max_minutes * 60
    left = a.max_pages
    for site in course.sites(cfg):
        if left <= 0 or time.time() > deadline:
            break
        res = course.digest_site(cfg, site, limit=left, idle_only=a.idle_only, deadline=deadline, tag="backlog", log=_log)
        left -= len(res)
        m = crawl.load_map(cfg, site)
        if res and not course.pending(m):  # just finished the last lesson of this site
            try:
                course.overview(cfg, site, log=_log)
            except Exception as exc:
                _log(f"{site}: overview failed: {exc}")
    return 0


def cmd_status(cfg, a) -> int:
    rows = []
    for site in course.sites(cfg):
        m = crawl.load_map(cfg, site)
        pages = m["pages"]
        dig = [p.get("digest") or {} for p in pages]
        rows.append({
            "site": site, "start_url": m["start_url"], "pages": len(pages),
            "mapped": sum(p["status"] == "mapped" for p in pages), "queued_to_map": sum(p["status"] == "queued" for p in pages),
            "lessons_to_digest": len(course.pending(m)), "digested": sum(d.get("status") in ("done", "partial") for d in dig),
            "failed": sum(d.get("status") == "failed" for d in dig), "videos": sum(len(p.get("videos") or []) for p in pages),
            "files": sum(len(p.get("docs") or []) for p in pages), "cost_usd": round(sum(d.get("cost_usd") or 0 for d in dig), 4),
            "logged_in": bool(session.load_state(cfg, site)),
        })
    print(json.dumps(rows, ensure_ascii=False, indent=1))
    return 0


def cmd_notion_setup(cfg, a) -> int:
    ds = notion_out.setup(a.parent, a.title)
    print(f"data source id: {ds}\nPut it in config.yaml under site: notion_data_source_id, or export SITEDIGEST_NOTION_DATA_SOURCE.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sitedigest", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("login")
    s.add_argument("url")
    s.add_argument("--site")
    s.add_argument("--auto", action="store_true", help="fill the form from SITEDIGEST_USER / SITEDIGEST_PASSWORD")
    s.set_defaults(fn=cmd_login)

    s = sub.add_parser("import-cookies")
    s.add_argument("file")
    s.add_argument("--site")
    s.add_argument("--url", help="derive the site name from this URL")
    s.set_defaults(fn=cmd_import)

    def crawl_args(s):
        s.add_argument("url")
        s.add_argument("--site")
        s.add_argument("--include", help="regex: only map URLs matching it (e.g. one course)")
        s.add_argument("--exclude", help="regex: never map URLs matching it")
        s.add_argument("--max-pages", type=int)

    s = sub.add_parser("map")
    crawl_args(s)
    s.add_argument("--host", action="append", help="extra host in scope (e.g. the course player domain)")
    s.add_argument("--max-depth", type=int, default=6)
    s.add_argument("--refresh", action="store_true", help="start the map again from scratch")
    s.add_argument("--show", action="store_true", help="visible browser")
    s.set_defaults(fn=cmd_map)

    s = sub.add_parser("outline")
    s.add_argument("site")
    s.add_argument("--out")
    s.set_defaults(fn=cmd_outline)

    s = sub.add_parser("digest")
    s.add_argument("site")
    s.add_argument("--page", action="append", help="page key or URL (repeatable); default: every lesson not done")
    s.add_argument("--limit", type=int)
    s.add_argument("--model", help="e.g. claude-code:sonnet for this run")
    s.add_argument("--no-notion", action="store_true")
    s.add_argument("--redo", action="store_true")
    s.add_argument("--all", action="store_true", help="also index/outline pages")
    s.set_defaults(fn=cmd_digest)

    s = sub.add_parser("fetch")
    s.add_argument("site")
    s.add_argument("--limit", type=int)
    s.add_argument("--include", help="regex on lesson URL or section (e.g. one course or module)")
    s.add_argument("--redo", action="store_true")
    s.add_argument("--show", action="store_true", help="visible browser")
    s.set_defaults(fn=cmd_fetch)

    s = sub.add_parser("pool")
    s.add_argument("site")
    s.add_argument("--workers", type=int, default=3)
    s.add_argument("--model", help="e.g. claude-code:sonnet")
    s.add_argument("--fallback-model", help="used while the main model's usage limit is hit (else the pool waits)")
    s.add_argument("--follow", action="store_true", help="keep picking up newly synced lessons until --max-minutes")
    s.add_argument("--require-vtt", action="store_true", help="only lessons whose prefetched videos have a transcript")
    s.add_argument("--include", help="regex on lesson URL or section")
    s.add_argument("--max-minutes", type=float, default=600)
    s.add_argument("--pause-minutes", type=float, default=30)
    s.add_argument("--no-notion", action="store_true")
    s.add_argument("--stats", action="store_true", help="only show the queue counts")
    s.set_defaults(fn=cmd_pool)

    s = sub.add_parser("course")
    s.add_argument("site")
    s.add_argument("--model")
    s.add_argument("--title")
    s.add_argument("--no-notion", action="store_true")
    s.set_defaults(fn=cmd_course)

    s = sub.add_parser("run")
    crawl_args(s)
    s.add_argument("--limit", type=int)
    s.add_argument("--model")
    s.add_argument("--no-notion", action="store_true")
    s.set_defaults(fn=cmd_run)

    s = sub.add_parser("worker")
    s.add_argument("--idle-only", action="store_true")
    s.add_argument("--max-pages", type=int, default=4)
    s.add_argument("--max-minutes", type=int, default=28)
    s.set_defaults(fn=cmd_worker)

    s = sub.add_parser("status")
    s.set_defaults(fn=cmd_status)

    s = sub.add_parser("notion-setup")
    s.add_argument("--parent", required=True, help="Notion page id to hold the database")
    s.add_argument("--title", default="Kursy: lekcje")
    s.set_defaults(fn=cmd_notion_setup)
    return p


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    cfg = config.load(a.config)
    return a.fn(cfg, a)
