#!/usr/bin/env python3
"""On prod (Hermes): queue a video digest for the PC pipeline (digest.py) and check on it.

  digest_request.py URL [URL ...] [--model sonnet|haiku] [--note "why"]   -> prints the job id
  digest_request.py --status [JOB]                                          -> state, Notion links

The PC (Windows task "Hermes digest queue", every 10 min) takes jobs from ~/.hermes/digest-queue/new, runs
download -> GPU transcript -> Sonnet on dev -> Notion, writes ~/.hermes/digest-queue/done/<job>.json and
pushes a notification with the Notion link to Filip. Dev sleeps at night for the prod upgrade, so a job can
take until the next afternoon; short videos usually take 10-30 min while everything is up.
"""

import argparse
import json
import re
import sys
import time
import uuid
from pathlib import Path

Q = Path.home() / ".hermes" / "digest-queue"
MODELS = {"sonnet": "claude-code:sonnet", "haiku": "claude-code:haiku"}
URL = re.compile(r"^https?://(www\.|m\.)?(youtube\.com|youtu\.be)/")


def status(job: str | None) -> int:
    rows = []
    for d in ("new", "running", "done"):
        for f in sorted((Q / d).glob("*.json")):
            j = json.loads(f.read_text(encoding="utf-8"))
            if job and j.get("job") != job:
                continue
            rows.append((d, j))
    if not rows:
        print("no such job" if job else "queue empty")
        return 1 if job else 0
    for d, j in rows[-10:]:
        print(f"{j['job']}  {d:7s}  {j.get('state', '')}  {', '.join(j.get('urls', []))[:90]}")
        r = j.get("result") or {}
        if r.get("overview"):
            print(f"    overview: {r['overview']}")
        for title, v in list((r.get("lessons") or {}).items())[:20]:
            print(f"    {v.get('status')}: {title[:60]} -> {v.get('notion')}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="*")
    ap.add_argument("--model", default="sonnet", choices=sorted(MODELS))
    ap.add_argument("--note", default="")
    ap.add_argument("--max", type=int, default=50, help="max videos per playlist/channel")
    ap.add_argument("--status", nargs="?", const="", default=None, metavar="JOB")
    a = ap.parse_args()
    for d in ("new", "running", "done"):
        (Q / d).mkdir(parents=True, exist_ok=True)
    if a.status is not None:
        return status(a.status or None)
    bad = [u for u in a.urls if not URL.match(u)]
    if not a.urls or bad:
        print("give YouTube links (video, playlist or channel)" + (f"; not YouTube: {bad}" if bad else ""))
        return 2
    job = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
    (Q / "new" / f"{job}.json").write_text(json.dumps({
        "job": job, "urls": a.urls, "model": MODELS[a.model], "max": a.max, "note": a.note,
        "requested": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "state": "queued"}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"{job} queued: {len(a.urls)} link(s), model {a.model}. Filip gets a notification with the Notion link "
          f"when it is done (minutes to hours; the dev VM sleeps at night). Status: digest_request.py --status {job}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
