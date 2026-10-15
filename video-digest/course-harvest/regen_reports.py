"""On the VM: rewrite lesson reports after the transcripts were redone on the PC (ASR v2:
course glossary + corrections). Only the transcript changes: page text, screenshot and
frame captions and files come from the saved lesson.json (videos are pruned, no new vision
calls). The first version is kept next to it: lesson.v1.json, report.v1.json, report.v1.md.

  python regen_reports.py SITE [--course-url-part X] [--workers 3] [--model claude-code:sonnet] [--follow]
A lesson is ready when its prefetch/*.vtt has the .asr2 marker (synced from the PC) and
report.v2 is not done yet (marker report.v2.done). --follow keeps waiting for new
transcripts until --idle-min minutes pass without one. Corrections from asr/*.json (same
files as on the PC) are applied to the transcript text here as well.

Slow mode (Filip, 2026-10-15: "slow rebuild", the Claude weekly limit is shared with his own work):
  --workers 1 --pause-sec 60 --daily-cap 80  -> one lesson at a time, a minute apart, at most 80 a day (UTC).
On a Claude limit it waits (1 h for the weekly limit, 15 min otherwise) and retries.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from sitedigest import config, crawl, lesson as L
from ytdigest import fetch, llm

LIMIT_RE = re.compile(r"limit|usage|quota|429|rate", re.I)


def fixes_for(site_dir: Path, course_url: str):
    f = site_dir / "asr" / f"{course_url.rstrip('/').rsplit('/', 1)[-1]}.json"
    if not f.is_file():
        return lambda t: t
    cfg = json.loads(f.read_text(encoding="utf-8"))
    fx: dict[str, str] = {}
    for extra in cfg.get("corrections_from") or []:
        fx.update(json.loads((f.parent / extra).read_text(encoding="utf-8")))
    fx.update(cfg.get("corrections") or {})
    fx = {k.lower(): v for k, v in fx.items()}
    if not fx:
        return lambda t: t
    rx = re.compile(r"(?<![\w-])(" + "|".join(sorted(map(re.escape, fx), key=len, reverse=True)) + r")(?![\w-])", re.I)
    return lambda t: rx.sub(lambda m: fx[m.group(0).lower()], t)


def ready(pdir: Path, rec: dict) -> bool:
    if (pdir / "report.v2.done").is_file() or not (pdir / "lesson.json").is_file():
        return False
    locs = [v[len("local:"):] for v in rec.get("videos") or [] if v.startswith("local:")]
    return bool(locs) and all(list((pdir / Path(v).parent).glob("*.vtt.asr2")) for v in locs)


def regen(cfg: dict, site: str, rec: dict, model: str, fix, log=print) -> dict:
    pdir = crawl.page_dir(cfg, site, rec["key"])
    for name in ("lesson.json", "report.json", "report.md"):
        old = pdir / name.replace(".", ".v1.", 1)
        if (pdir / name).is_file() and not old.is_file():
            shutil.copy2(pdir / name, old)
    lesson = json.loads((pdir / "lesson.v1.json").read_text(encoding="utf-8"))
    prev = json.loads((pdir / "report.v1.json").read_text(encoding="utf-8"))
    locs = [v[len("local:"):] for v in rec.get("videos") or [] if v.startswith("local:")]
    for v, loc in zip(lesson["videos"], locs):
        vtts = sorted((pdir / Path(loc).parent).glob("*.vtt"))
        if vtts:
            segs = fetch.parse_vtt(vtts[0].read_text(encoding="utf-8", errors="replace"))
            for s in segs:
                s["text"] = fix(s["text"])
            v["transcript"] = {"source": "player_captions", "language": vtts[0].name.split(".")[-2][:2],
                               "segments": segs, "asr": "v2 (course glossary)"}
    client = llm.Client(cfg, ledger=Path(cfg["data_dir"]) / "spend.jsonl", tag="regen-v2")
    started = datetime.now(timezone.utc)
    user = f"Course site: {site}\nSection: {lesson['section']}\nLesson: {lesson['title']}\nURL: {lesson['url']}\n\n" \
           f"{L._sources(client, model, cfg, lesson)}\n\n{L._instructions(cfg)}"
    rep = L.normalise(client.json(model, L.SYSTEM, user, max_tokens=6000))
    if any(v["status"] != "done" for v in lesson["videos"]):
        rep["confidence"] = min(rep["confidence"], 0.6)
    run = {**(prev.get("run") or {}), "regen": "v2: transcript with course glossary", "report_model": model,
           "regen_started": started.isoformat(), "models": client.usage.models, "cost_usd": client.usage.cost_usd,
           "usage": client.usage.by_model, "seconds": round((datetime.now(timezone.utc) - started).total_seconds(), 1)}
    status = (rec.get("digest") or {}).get("status") or "done"
    (pdir / "lesson.json").write_text(json.dumps(lesson, ensure_ascii=False, indent=1), encoding="utf-8")
    (pdir / "report.json").write_text(json.dumps({"report": rep, "run": run}, ensure_ascii=False, indent=1), encoding="utf-8")
    from sitedigest import notion_out
    (pdir / "report.md").write_text(notion_out.markdown(lesson, rep, run, None), encoding="utf-8")
    (pdir / "report.v2.done").write_text(started.isoformat(), encoding="utf-8")
    return {"key": rec["key"], "title": lesson["title"], "seconds": run["seconds"], "status": status}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("site")
    ap.add_argument("--course-url-part", action="append", default=[])
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--model", default="claude-code:sonnet")
    ap.add_argument("--follow", action="store_true")
    ap.add_argument("--idle-min", type=int, default=120)
    ap.add_argument("--pause-sec", type=int, default=0, help="rest between lessons (per worker)")
    ap.add_argument("--daily-cap", type=int, default=0, help="max v2 reports per UTC day (0 = no cap)")
    a = ap.parse_args()
    cfg = config.load()
    site_dir = crawl.map_path(cfg, a.site).parent
    busy: set[str] = set()
    lock = threading.Lock()
    pause_until = [0.0]
    idle_since = time.time()

    def one(rec: dict) -> None:
        try:
            while time.time() < pause_until[0]:
                time.sleep(30)
            r = regen(cfg, a.site, rec, a.model, fixes_for(site_dir, rec.get("course_url", "")))
            print(time.strftime("%H:%M:%S"), f"v2 {r['key']} {r['title'][:60]} ({r['seconds']} s)", flush=True)
            time.sleep(a.pause_sec)
        except Exception as exc:
            msg = f"{type(exc).__name__}: {str(exc)[:300]}"
            print(time.strftime("%H:%M:%S"), f"FAIL {rec['key']} {rec.get('title', '')[:50]}: {msg}", flush=True)
            if LIMIT_RE.search(msg):
                # Claude limit: wait, the lesson is retried
                pause_until[0] = time.time() + (3600 if "weekly" in msg.lower() else 900)
        finally:
            with lock:
                busy.discard(rec["key"])

    def done_today() -> int:
        day = datetime.now(timezone.utc).date()
        return sum(1 for f in (site_dir / "pages").glob("*/report.v2.done")
                   if datetime.fromtimestamp(f.stat().st_mtime, timezone.utc).date() == day)

    with ThreadPoolExecutor(a.workers) as ex:
        while True:
            if a.daily_cap and done_today() >= a.daily_cap:
                time.sleep(600)  # cap reached: wait for the next UTC day
                idle_since = time.time()
                continue
            m = crawl.load_map(cfg, a.site)
            todo = [p for p in m["pages"] if (p.get("digest") or {}).get("status") in ("done", "partial")
                    and (not a.course_url_part or any(c in p.get("course_url", "") for c in a.course_url_part))
                    and p["key"] not in busy and ready(crawl.page_dir(cfg, a.site, p["key"]), p)]
            for p in todo[: max(0, a.workers - len(busy))]:
                with lock:
                    busy.add(p["key"])
                ex.submit(one, p)
            if todo:
                idle_since = time.time()
            elif not busy and (not a.follow or time.time() - idle_since > a.idle_min * 60):
                break
            time.sleep(20)
    left = sum(1 for p in crawl.load_map(cfg, a.site)["pages"]
               if (p.get("digest") or {}).get("status") in ("done", "partial")
               and not (crawl.page_dir(cfg, a.site, p["key"]) / "report.v2.done").is_file())
    print(f"finished; digested lessons without a v2 report: {left}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
